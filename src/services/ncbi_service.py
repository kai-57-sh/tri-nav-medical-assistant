"""NCBI service for PubMed literature retrieval."""
import httpx
import re
from typing import List, Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from datetime import datetime
from ..config.settings import get_settings
from ..utils.logging_config import get_logger
from ..utils.metrics import set_external_service_health

logger = get_logger(__name__)

settings = get_settings()


class NCBIService:
    """NCBI E-utilities integration for PubMed literature retrieval.

    Implements graceful degradation per FR-032.
    """

    def __init__(self):
        """Initialize NCBI service."""
        self.base_url = settings.ncbi_base_url
        self._healthy = True
        self._timeout = settings.ncbi_timeout
        self._tool = "TriNav"
        self._email = "trinav@example.com"  # Should be configured

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=3)
    )
    async def _make_request(
        self,
        endpoint: str,
        params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Make HTTP request to NCBI E-utilities API with retry.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            Response JSON or None on failure
        """
        url = f"{self.base_url}/{endpoint}"

        # Add required parameters
        params["tool"] = self._tool
        params["email"] = self._email
        params["retmode"] = "json"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                result = response.json()

                self._healthy = True
                set_external_service_health("ncbi", True)
                return result

        except httpx.TimeoutException:
            self._healthy = False
            set_external_service_health("ncbi", False)
            logger.warning(f"NCBI API timeout: {endpoint}")
            return None

        except httpx.HTTPError as e:
            self._healthy = False
            set_external_service_health("ncbi", False)
            logger.error(f"NCBI API HTTP error: {e}")
            return None

        except Exception as e:
            self._healthy = False
            set_external_service_health("ncbi", False)
            logger.error(f"NCBI API unexpected error: {e}")
            return None

    async def search_pubmed(
        self,
        query: str,
        max_results: int = 20
    ) -> List[str]:
        """Search PubMed for articles matching query.

        Filters: Last 10 years, preference for guidelines/reviews per FR-030.

        Args:
            query: Search query string
            max_results: Maximum number of PMIDs to return

        Returns:
            List of PubMed IDs (PMIDs)
        """
        # Build search query with date filter
        current_year = datetime.now().year
        min_year = current_year - 10
        date_filter = f"{min_year}:3000[dpcr]"  # Publication date filter

        full_query = f"{query} AND {date_filter}"

        params = {
            "db": "pubmed",
            "term": full_query,
            "retmax": max_results,
            "sort": "relevance",
            "filter": "hasabstract"  # Only include articles with abstracts
        }

        result = await self._make_request("esearch.fcgi", params)

        if not result or "esearchresult" not in result:
            logger.warning(f"No PubMed results for query: {query}")
            return []

        try:
            pmids = result["esearchresult"].get("idlist", [])
            logger.info(f"Found {len(pmids)} articles for query", extra={"query": query})
            return pmids

        except (KeyError, TypeError) as e:
            logger.error(f"Failed to parse PubMed search results: {e}")
            return []

    async def fetch_article_details(
        self,
        pmid_list: List[str]
    ) -> List[Dict[str, Any]]:
        """Fetch detailed information for list of PMIDs.

        Args:
            pmid_list: List of PubMed IDs

        Returns:
            List of article detail dicts
        """
        if not pmid_list:
            return []

        params = {
            "db": "pubmed",
            "id": ",".join(pmid_list),
            "rettype": "abstract"
        }

        result = await self._make_request("esummary.fcgi", params)

        if not result or "result" not in result:
            logger.warning("Failed to fetch article details")
            return []

        try:
            articles = []
            result_data = result["result"]

            for pmid in pmid_list:
                if pmid not in result_data:
                    continue

                article_data = result_data[pmid]
                article = self._parse_article(pmid, article_data)

                if article:
                    articles.append(article)

            logger.info(f"Fetched details for {len(articles)} articles")
            return articles

        except (KeyError, TypeError) as e:
            logger.error(f"Failed to parse article details: {e}")
            return []

    def _parse_article(
        self,
        pmid: str,
        data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Parse article data from NCBI response.

        Args:
            pmid: PubMed ID
            data: Article data from NCBI

        Returns:
            Article dict or None
        """
        try:
            title = data.get("title", "")
            if not title:
                return None

            # Extract publication year
            pub_date = data.get("pubdate", "")
            year_match = re.search(r"(\d{4})", pub_date)
            year = year_match.group(1) if year_match else "Unknown"

            # Extract source (journal)
            source = ""
            if "source" in data:
                source = data["source"]
            elif "authors" in data and data["authors"]:
                # Fallback to first author's affiliation
                authors = data["authors"]
                if authors and len(authors) > 0:
                    source = "Unknown Journal"

            # Determine article type based on title/publication
            article_type = self._classify_article_type(title, source)

            return {
                "pmid": pmid,
                "title": title,
                "year": year,
                "source": source,
                "type": article_type
            }

        except (KeyError, AttributeError) as e:
            logger.warning(f"Failed to parse article {pmid}: {e}")
            return None

    def _classify_article_type(self, title: str, source: str) -> str:
        """Classify article type based on title and journal.

        Preference: Guidelines > Systematic Reviews > Reviews > RCT > Case Reports

        Args:
            title: Article title
            source: Journal name

        Returns:
            Article type string
        """
        title_lower = title.lower()
        source_lower = source.lower()

        # Check for guidelines
        if any(keyword in title_lower for keyword in [
            "guideline", "指南", "recommendation", "建议", "consensus"
        ]):
            return "Guideline"

        # Check for systematic reviews
        if any(keyword in title_lower for keyword in [
            "systematic review", "meta-analysis", "系统综述", "荟萃分析"
        ]):
            return "SystematicReview"

        # Check for reviews
        if any(keyword in title_lower for keyword in [
            "review", "综述", "overview", "进展"
        ]):
            return "Review"

        # Check for RCTs
        if any(keyword in title_lower for keyword in [
            "randomized", "clinical trial", "随机对照", "rct"
        ]):
            return "RCT"

        # Check for case reports
        if any(keyword in title_lower for keyword in [
            "case report", "病例报告", "case study"
        ]):
            return "CaseReport"

        # Default to Other
        return "Other"

    async def search_and_retrieve(
        self,
        query: str,
        max_results: int = 8
    ) -> List[Dict[str, Any]]:
        """Search PubMed and retrieve article details in one call.

        Args:
            query: Search query
            max_results: Maximum number of articles to return (5-8 per FR-031)

        Returns:
            List of article dicts sorted by relevance and type
        """
        # Search for PMIDs
        pmids = await self.search_pubmed(query, max_results=20)

        if not pmids:
            return []

        # Fetch article details
        articles = await self.fetch_article_details(pmids)

        if not articles:
            return []

        # Rank articles by type preference
        type_priority = {
            "Guideline": 1,
            "SystematicReview": 2,
            "Review": 3,
            "RCT": 4,
            "CaseReport": 5,
            "Other": 6
        }

        # Sort by type priority, then by year (newer first)
        articles.sort(key=lambda a: (
            type_priority.get(a.get("type", "Other"), 6),
            -int(a.get("year", "0"))
        ))

        # Return top N results (5-8 per FR-031)
        return articles[:max_results]

    @property
    def is_healthy(self) -> bool:
        """Check if NCBI service is healthy."""
        return self._healthy


# Global NCBI service instance
_ncbi_service: Optional[NCBIService] = None


def get_ncbi_service() -> NCBIService:
    """Get or create global NCBI service instance.

    Returns:
        NCBIService instance
    """
    global _ncbi_service

    if _ncbi_service is None:
        _ncbi_service = NCBIService()

    return _ncbi_service
