"""Tests for NavigationResult model and validation rules."""
import pytest
from pydantic import ValidationError

from src.models.navigation_result import NavigationResult, Hospital, RoutePlan


class TestRoutePlan:
    """Test RoutePlan validation."""

    def test_route_plan_valid_driving(self):
        """Test valid route plan with driving mode."""
        route = RoutePlan(
            to_hospital_rank=1,
            mode="driving",
            eta_min=15,
            summary="大约15分钟车程"
        )
        assert route.to_hospital_rank == 1
        assert route.mode == "driving"
        assert route.eta_min == 15
        assert route.summary == "大约15分钟车程"

    def test_route_plan_valid_transit(self):
        """Test valid route plan with transit mode."""
        route = RoutePlan(
            to_hospital_rank=1,
            mode="transit",
            eta_min=30,
            summary="乘坐地铁约30分钟"
        )
        assert route.mode == "transit"

    def test_route_plan_valid_walking(self):
        """Test valid route plan with walking mode."""
        route = RoutePlan(
            to_hospital_rank=1,
            mode="walking",
            eta_min=45,
            summary="步行约45分钟"
        )
        assert route.mode == "walking"

    def test_route_plan_invalid_rank_zero(self):
        """Test rank cannot be 0."""
        with pytest.raises(ValidationError) as exc_info:
            RoutePlan(
                to_hospital_rank=0,
                mode="driving",
                eta_min=15,
                summary="15分钟"
            )
        assert "to_hospital_rank" in str(exc_info.value)

    def test_route_plan_invalid_rank_four(self):
        """Test rank cannot be 4."""
        with pytest.raises(ValidationError) as exc_info:
            RoutePlan(
                to_hospital_rank=4,
                mode="driving",
                eta_min=15,
                summary="15分钟"
            )
        assert "to_hospital_rank" in str(exc_info.value)

    def test_route_plan_invalid_mode(self):
        """Test invalid transport mode."""
        with pytest.raises(ValidationError) as exc_info:
            RoutePlan(
                to_hospital_rank=1,
                mode="biking",  # Invalid mode
                eta_min=15,
                summary="15分钟"
            )
        assert "mode" in str(exc_info.value)

    def test_route_plan_invalid_eta_zero(self):
        """Test eta cannot be 0."""
        with pytest.raises(ValidationError) as exc_info:
            RoutePlan(
                to_hospital_rank=1,
                mode="driving",
                eta_min=0,
                summary="15分钟"
            )
        assert "eta_min" in str(exc_info.value)

    def test_route_plan_invalid_eta_negative(self):
        """Test eta cannot be negative."""
        with pytest.raises(ValidationError) as exc_info:
            RoutePlan(
                to_hospital_rank=1,
                mode="driving",
                eta_min=-5,
                summary="15分钟"
            )
        assert "eta_min" in str(exc_info.value)

    def test_route_plan_empty_summary(self):
        """Test summary cannot be empty."""
        with pytest.raises(ValidationError) as exc_info:
            RoutePlan(
                to_hospital_rank=1,
                mode="driving",
                eta_min=15,
                summary=""
            )
        assert "summary" in str(exc_info.value)

    def test_route_plan_summary_too_long(self):
        """Test summary max length 200."""
        with pytest.raises(ValidationError) as exc_info:
            RoutePlan(
                to_hospital_rank=1,
                mode="driving",
                eta_min=15,
                summary="a" * 201
            )
        assert "summary" in str(exc_info.value)


class TestHospital:
    """Test Hospital validation."""

    def test_hospital_valid_complete(self):
        """Test valid hospital with all fields."""
        hospital = Hospital(
            rank=1,
            name="北京协和医院",
            is_3a=True,
            address="北京市东城区帅府园1号",
            distance_m=1200,
            location={"lat": 39.914, "lng": 116.417},
            phone="010-69156699",
            reason="三甲综合医院，距离较近，急诊/门诊齐全"
        )
        assert hospital.rank == 1
        assert hospital.name == "北京协和医院"
        assert hospital.is_3a is True
        assert hospital.distance_m == 1200

    def test_hospital_valid_minimal(self):
        """Test valid hospital with minimal required fields."""
        hospital = Hospital(
            rank=2,
            name="朝阳医院",
            is_3a=False,
            location={"lat": 39.921, "lng": 116.457},
            reason="距离较近，可作为备选"
        )
        assert hospital.address is None
        assert hospital.distance_m is None
        assert hospital.phone is None

    def test_hospital_invalid_rank_zero(self):
        """Test rank cannot be 0."""
        with pytest.raises(ValidationError) as exc_info:
            Hospital(
                rank=0,
                name="Test Hospital",
                is_3a=True,
                location={"lat": 39.9, "lng": 116.4},
                reason="Test"
            )
        assert "rank" in str(exc_info.value)

    def test_hospital_invalid_rank_four(self):
        """Test rank cannot be 4."""
        with pytest.raises(ValidationError) as exc_info:
            Hospital(
                rank=4,
                name="Test Hospital",
                is_3a=True,
                location={"lat": 39.9, "lng": 116.4},
                reason="Test"
            )
        assert "rank" in str(exc_info.value)

    def test_hospital_invalid_name_too_long(self):
        """Test name max length 100."""
        with pytest.raises(ValidationError) as exc_info:
            Hospital(
                rank=1,
                name="a" * 101,
                is_3a=True,
                location={"lat": 39.9, "lng": 116.4},
                reason="Test"
            )
        assert "name" in str(exc_info.value)

    def test_hospital_invalid_address_too_long(self):
        """Test address max length 200."""
        with pytest.raises(ValidationError) as exc_info:
            Hospital(
                rank=1,
                name="Test Hospital",
                is_3a=True,
                address="a" * 201,
                location={"lat": 39.9, "lng": 116.4},
                reason="Test"
            )
        assert "address" in str(exc_info.value)

    def test_hospital_invalid_negative_distance(self):
        """Test distance cannot be negative."""
        with pytest.raises(ValidationError) as exc_info:
            Hospital(
                rank=1,
                name="Test Hospital",
                is_3a=True,
                distance_m=-100,
                location={"lat": 39.9, "lng": 116.4},
                reason="Test"
            )
        assert "distance_m" in str(exc_info.value)

    def test_hospital_invalid_phone_too_long(self):
        """Test phone max length 50."""
        with pytest.raises(ValidationError) as exc_info:
            Hospital(
                rank=1,
                name="Test Hospital",
                is_3a=True,
                location={"lat": 39.9, "lng": 116.4},
                phone="a" * 51,
                reason="Test"
            )
        assert "phone" in str(exc_info.value)

    def test_hospital_invalid_reason_empty(self):
        """Test reason cannot be empty."""
        with pytest.raises(ValidationError) as exc_info:
            Hospital(
                rank=1,
                name="Test Hospital",
                is_3a=True,
                location={"lat": 39.9, "lng": 116.4},
                reason=""
            )
        assert "reason" in str(exc_info.value)

    def test_hospital_invalid_reason_too_long(self):
        """Test reason max length 200."""
        with pytest.raises(ValidationError) as exc_info:
            Hospital(
                rank=1,
                name="Test Hospital",
                is_3a=True,
                location={"lat": 39.9, "lng": 116.4},
                reason="a" * 201
            )
        assert "reason" in str(exc_info.value)


class TestNavigationResult:
    """Test NavigationResult validation rules."""

    def test_navigation_result_valid_complete(self):
        """Test valid navigation result with route plan."""
        hospitals = [
            Hospital(
                rank=1,
                name="北京协和医院",
                is_3a=True,
                address="北京市东城区帅府园1号",
                distance_m=1200,
                location={"lat": 39.914, "lng": 116.417},
                phone="010-69156699",
                reason="三甲综合医院，距离较近，急诊/门诊齐全"
            ),
            Hospital(
                rank=2,
                name="中日友好医院",
                is_3a=True,
                address="北京市朝阳区樱花园东街",
                distance_m=3500,
                location={"lat": 39.979, "lng": 116.447},
                reason="三甲综合医院，口碑较好"
            ),
            Hospital(
                rank=3,
                name="朝阳医院",
                is_3a=False,
                address="北京市朝阳区工人体育场南路",
                distance_m=900,
                location={"lat": 39.921, "lng": 116.457},
                reason="距离更近，可作为备选"
            )
        ]

        route = RoutePlan(
            to_hospital_rank=1,
            mode="driving",
            eta_min=15,
            summary="大约15分钟车程"
        )

        nav_result = NavigationResult(
            radius_km=10,
            hospitals=hospitals,
            route_plan=route
        )

        assert nav_result.radius_km == 10
        assert len(nav_result.hospitals) == 3
        assert nav_result.route_plan is not None

    def test_navigation_result_valid_without_route(self):
        """Test valid navigation result without route plan."""
        hospitals = [
            Hospital(
                rank=1,
                name="医院1",
                is_3a=True,
                location={"lat": 39.9, "lng": 116.4},
                reason="Test1"
            ),
            Hospital(
                rank=2,
                name="医院2",
                is_3a=False,
                location={"lat": 39.91, "lng": 116.41},
                reason="Test2"
            ),
            Hospital(
                rank=3,
                name="医院3",
                is_3a=False,
                location={"lat": 39.92, "lng": 116.42},
                reason="Test3"
            )
        ]

        nav_result = NavigationResult(radius_km=10, hospitals=hospitals)
        assert nav_result.route_plan is None

    def test_navigation_result_exactly_three_hospitals_pass(self):
        """Test validator: exactly 3 hospitals passes."""
        hospitals = [
            Hospital(rank=i, name=f"医院{i}", is_3a=True, location={"lat": 39.9, "lng": 116.4}, reason=f"Test{i}")
            for i in [1, 2, 3]
        ]
        nav_result = NavigationResult(radius_km=10, hospitals=hospitals)
        assert len(nav_result.hospitals) == 3

    def test_navigation_result_exactly_three_hospitals_fail_two(self):
        """Test validator: 2 hospitals fails with Pydantic v2 error."""
        hospitals = [
            Hospital(rank=i, name=f"医院{i}", is_3a=True, location={"lat": 39.9, "lng": 116.4}, reason=f"Test{i}")
            for i in [1, 2]
        ]
        with pytest.raises(ValidationError) as exc_info:
            NavigationResult(radius_km=10, hospitals=hospitals)
        # Pydantic v2 error: "List should have at least 3 items"
        assert "at least 3 items" in str(exc_info.value)

    def test_navigation_result_exactly_three_hospitals_fail_four(self):
        """Test validator: 4 hospitals fails with Pydantic v2 error."""
        hospitals = [
            Hospital(rank=i if i <= 3 else 3, name=f"医院{i}", is_3a=True, location={"lat": 39.9, "lng": 116.4}, reason=f"Test{i}")
            for i in [1, 2, 3, 4]
        ]
        with pytest.raises(ValidationError) as exc_info:
            NavigationResult(radius_km=10, hospitals=hospitals)
        # Pydantic v2 error: "List should have at most 3 items"
        assert "at most 3 items" in str(exc_info.value)

    def test_navigation_result_ranked_correctly_pass(self):
        """Test validator: ranks 1,2,3 passes."""
        hospitals = [
            Hospital(rank=1, name="医院1", is_3a=True, location={"lat": 39.9, "lng": 116.4}, reason="Test1"),
            Hospital(rank=2, name="医院2", is_3a=True, location={"lat": 39.91, "lng": 116.41}, reason="Test2"),
            Hospital(rank=3, name="医院3", is_3a=True, location={"lat": 39.92, "lng": 116.42}, reason="Test3")
        ]
        nav_result = NavigationResult(radius_km=10, hospitals=hospitals)
        assert [h.rank for h in nav_result.hospitals] == [1, 2, 3]

    def test_navigation_result_ranked_correctly_fail_duplicates(self):
        """Test validator: duplicate ranks fail."""
        hospitals = [
            Hospital(rank=1, name="医院1", is_3a=True, location={"lat": 39.9, "lng": 116.4}, reason="Test1"),
            Hospital(rank=1, name="医院2", is_3a=True, location={"lat": 39.91, "lng": 116.41}, reason="Test2"),
            Hospital(rank=3, name="医院3", is_3a=True, location={"lat": 39.92, "lng": 116.42}, reason="Test3")
        ]
        with pytest.raises(ValidationError) as exc_info:
            NavigationResult(radius_km=10, hospitals=hospitals)
        assert "Hospitals must be ranked 1, 2, 3" in str(exc_info.value)

    def test_navigation_result_ranked_correctly_fail_wrong_sequence(self):
        """Test validator: rank=4 fails Hospital validation before NavigationResult."""
        # rank must be <= 3 at Hospital level
        with pytest.raises(ValidationError) as exc_info:
            Hospital(
                rank=4,
                name="医院3",
                is_3a=True,
                location={"lat": 39.92, "lng": 116.42},
                reason="Test3"
            )
        # Pydantic v2 error: "Input should be less than or equal to 3"
        assert "less than or equal to 3" in str(exc_info.value)

    def test_navigation_result_radius_default(self):
        """Test radius_km defaults to 10."""
        hospitals = [
            Hospital(rank=i, name=f"医院{i}", is_3a=True, location={"lat": 39.9, "lng": 116.4}, reason=f"Test{i}")
            for i in [1, 2, 3]
        ]
        nav_result = NavigationResult(hospitals=hospitals)
        assert nav_result.radius_km == 10

    def test_navigation_result_invalid_radius_zero(self):
        """Test radius_km cannot be 0."""
        hospitals = [
            Hospital(rank=i, name=f"医院{i}", is_3a=True, location={"lat": 39.9, "lng": 116.4}, reason=f"Test{i}")
            for i in [1, 2, 3]
        ]
        with pytest.raises(ValidationError) as exc_info:
            NavigationResult(radius_km=0, hospitals=hospitals)
        assert "radius_km" in str(exc_info.value)

    def test_navigation_result_invalid_radius_too_large(self):
        """Test radius_km max is 50."""
        hospitals = [
            Hospital(rank=i, name=f"医院{i}", is_3a=True, location={"lat": 39.9, "lng": 116.4}, reason=f"Test{i}")
            for i in [1, 2, 3]
        ]
        with pytest.raises(ValidationError) as exc_info:
            NavigationResult(radius_km=51, hospitals=hospitals)
        assert "radius_km" in str(exc_info.value)

    def test_navigation_result_json_serialization(self):
        """Test NavigationResult can be serialized to JSON."""
        hospitals = [
            Hospital(
                rank=1,
                name="Test Hospital",
                is_3a=True,
                location={"lat": 39.9, "lng": 116.4},
                reason="Test reason"
            ),
            Hospital(
                rank=2,
                name="Hospital 2",
                is_3a=False,
                location={"lat": 39.91, "lng": 116.41},
                reason="Test2"
            ),
            Hospital(
                rank=3,
                name="Hospital 3",
                is_3a=False,
                location={"lat": 39.92, "lng": 116.42},
                reason="Test3"
            )
        ]

        nav_result = NavigationResult(
            radius_km=10,
            hospitals=hospitals,
            route_plan=RoutePlan(
                to_hospital_rank=1,
                mode="driving",
                eta_min=15,
                summary="15分钟"
            )
        )

        # Test model_dump
        data = nav_result.model_dump()
        assert "hospitals" in data
        assert len(data["hospitals"]) == 3
        assert data["radius_km"] == 10

        # Test JSON serialization
        json_str = nav_result.model_dump_json()
        assert "Test Hospital" in json_str
