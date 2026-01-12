import { useState, useRef, useEffect } from 'react';
import {
  Send,
  Plus,
  Image as ImageIcon,
  MapPin,
  Moon,
  Sun,
  MoreVertical,
  Trash2,
} from 'lucide-react';
import { TriageCard } from './components/triage/TriageCard';
import { HospitalCard } from './components/triage/HospitalCard';
import { Disclaimer } from './components/triage/Disclaimer';
import { apiClient } from './lib/api';
import { generateUUID, cn } from './lib/utils';
import type { Message } from './lib/types';
import ReactMarkdown from 'react-markdown';
import { Clock } from 'lucide-react';

// 会话历史类型
interface Session {
  id: string;
  title: string;
  createdAt: Date;
  messages: Message[];
}

// 医院请求关键词检测
const isHospitalRequest = (text: string): boolean => {
  const positiveKeywords = ['医院', '就医', '导航', '推荐医院', '挂号', '急诊'];
  const negativeKeywords = ['不去医院', '不想去医院', '无需就医'];

  const hasPositive = positiveKeywords.some(kw => text.includes(kw));
  const hasNegative = negativeKeywords.some(kw => text.includes(kw));

  return hasPositive && !hasNegative;
};

function App() {
  const [sessions, setSessions] = useState<Session[]>([
    {
      id: generateUUID(),
      title: '新对话',
      createdAt: new Date(),
      messages: [],
    },
  ]);
  const [currentSessionId, setCurrentSessionId] = useState(sessions[0].id);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [imageData, setImageData] = useState<string | null>(null);
  const [gpsLocation, setGpsLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 当前会话
  const currentSession = sessions.find((s) => s.id === currentSessionId) || sessions[0];

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentSession.messages]);

  // 主题切换
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  // 发送消息
  const handleSend = async () => {
    if (!input.trim() && !imageData) return;
    if (isLoading) return;

    // 新增：医院请求且无 GPS 时，引导定位
    if (isHospitalRequest(input) && !gpsLocation) {
      const locationPrompt: Message = {
        id: generateUUID(),
        role: 'assistant',
        content: '需要定位才能推荐医院。请点击右上角的定位按钮获取位置后，重新发送医院请求。',
        timestamp: new Date(),
      };

      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === currentSessionId) {
            return { ...s, messages: [...s.messages, locationPrompt] };
          }
          return s;
        })
      );

      setInput('');  // 清空输入，用户需要重新发送
      return;
    }

    const userMessage: Message = {
      id: generateUUID(),
      role: 'user',
      content: input,
      timestamp: new Date(),
      image: imageData || undefined,
    };

    // 更新会话
    const updatedSessions = sessions.map((s) => {
      if (s.id === currentSessionId) {
        const newMessages = [...s.messages, userMessage];
        const title = s.title === '新对话' && input.length > 0
          ? input.slice(0, 20) + (input.length > 20 ? '...' : '')
          : s.title;
        return { ...s, messages: newMessages, title };
      }
      return s;
    });
    setSessions(updatedSessions);

    setInput('');
    setImageData(null);
    setIsLoading(true);

    try {
      const response = await apiClient.sendTriageMessage({
        session_id: currentSessionId,
        text: userMessage.content,
        image_base64: userMessage.image,
        gps_lat: gpsLocation?.lat,
        gps_lng: gpsLocation?.lng,
      });

      const assistantMessage: Message = {
        id: generateUUID(),
        role: 'assistant',
        content: response.response || '',
        timestamp: new Date(),
        triageData: response,
      };

      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === currentSessionId) {
            return { ...s, messages: [...s.messages, assistantMessage] };
          }
          return s;
        })
      );
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMessage: Message = {
        id: generateUUID(),
        role: 'assistant',
        content: '抱歉，发生了错误。请检查后端服务是否正常运行，然后重试。',
        timestamp: new Date(),
      };
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id === currentSessionId) {
            return { ...s, messages: [...s.messages, errorMessage] };
          }
          return s;
        })
      );
    } finally {
      setIsLoading(false);
    }
  };

  // 新建会话
  const handleNewSession = () => {
    const newSession: Session = {
      id: generateUUID(),
      title: '新对话',
      createdAt: new Date(),
      messages: [],
    };
    setSessions([newSession, ...sessions]);
    setCurrentSessionId(newSession.id);
    setImageData(null);
    setGpsLocation(null);
  };

  // 删除会话
  const handleDeleteSession = (sessionId: string) => {
    const filtered = sessions.filter((s) => s.id !== sessionId);
    if (filtered.length === 0) {
      handleNewSession();
      return;
    }
    setSessions(filtered);
    if (currentSessionId === sessionId) {
      setCurrentSessionId(filtered[0].id);
    }
  };

  // 图片上传
  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // 检查文件大小 (5MB)
    if (file.size > 5 * 1024 * 1024) {
      alert('图片大小不能超过 5MB');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const result = e.target?.result as string;
      // 只保留 base64 部分
      const base64 = result.split(',')[1];
      setImageData(base64);
    };
    reader.readAsDataURL(file);
  };

  // 获取 GPS 位置
  const handleGetLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setGpsLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
          alert(`已获取位置: ${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`);
        },
        (error) => {
          alert('获取位置失败: ' + error.message);
        }
      );
    } else {
      alert('您的浏览器不支持地理定位');
    }
  };

  // 处理键盘事件
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // 地图导航
  const handleNavigate = (hospital: any) => {
    window.open(`https://www.google.com/maps/dir/?api=1&destination=${hospital.location.lat},${hospital.location.lng}`, '_blank');
  };

  return (
    <div className="flex h-screen bg-background text-foreground">
      {/* 侧边栏 */}
      {showSidebar && (
        <div className="w-72 bg-card border-r border-border flex flex-col">
          {/* 头部 */}
          <div className="p-4 border-b border-border">
            <button
              onClick={handleNewSession}
              className="w-full flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-opacity"
            >
              <Plus className="w-4 h-4" />
              新对话
            </button>
          </div>

          {/* 会话列表 */}
          <div className="flex-1 overflow-y-auto p-2 space-y-1 scrollbar-thin">
            {sessions.map((session) => (
              <div
                key={session.id}
                className={cn(
                  'group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors',
                  currentSessionId === session.id
                    ? 'bg-muted'
                    : 'hover:bg-muted/50'
                )}
                onClick={() => setCurrentSessionId(session.id)}
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{session.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {session.messages.length} 条消息
                  </p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteSession(session.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:bg-muted rounded transition-opacity"
                >
                  <Trash2 className="w-3 h-3 text-muted-foreground" />
                </button>
              </div>
            ))}
          </div>

          {/* 底部 */}
          <div className="p-4 border-t border-border">
            <div className="text-xs text-muted-foreground">
              TriNav 医疗分诊助手
            </div>
          </div>
        </div>
      )}

      {/* 主内容区 */}
      <div className="flex-1 flex flex-col">
        {/* 顶部栏 */}
        <div className="h-14 border-b border-border flex items-center justify-between px-4 bg-card">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSidebar(!showSidebar)}
              className="p-2 hover:bg-muted rounded-lg transition-colors"
            >
              <MoreVertical className="w-5 h-5" />
            </button>
            <h1 className="font-semibold">TriNav 医疗分诊</h1>
          </div>
          <div className="flex items-center gap-2">
            {gpsLocation && (
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <MapPin className="w-3 h-3" />
                已定位
              </span>
            )}
            <button
              onClick={() => setIsDarkMode(!isDarkMode)}
              className="p-2 hover:bg-muted rounded-lg transition-colors"
            >
              {isDarkMode ? (
                <Sun className="w-5 h-5" />
              ) : (
                <Moon className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>

        {/* 消息区域 */}
        <div className="flex-1 overflow-y-auto p-4 scrollbar-thin">
          <div className="max-w-3xl mx-auto space-y-4">
            {/* 欢迎消息 */}
            {currentSession.messages.length === 0 && (
              <div className="text-center py-12">
                <div className="text-6xl mb-4">🏥</div>
                <h2 className="text-2xl font-bold mb-2">欢迎使用 TriNav 医疗分诊助手</h2>
                <p className="text-muted-foreground mb-8">
                  请描述您的症状，我会为您进行初步分诊评估
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-md mx-auto text-left">
                  <button
                    onClick={() => setInput('我发烧了，体温39度，伴有头痛')}
                    className="p-3 bg-muted hover:bg-muted/80 rounded-lg text-sm transition-colors"
                  >
                    🤒 我发烧了，体温39度，伴有头痛
                  </button>
                  <button
                    onClick={() => setInput('我肚子疼，主要是右下腹疼')}
                    className="p-3 bg-muted hover:bg-muted/80 rounded-lg text-sm transition-colors"
                  >
                    🤢 我肚子疼，主要是右下腹疼
                  </button>
                  <button
                    onClick={() => setInput('我胸口闷，呼吸有点困难')}
                    className="p-3 bg-muted hover:bg-muted/80 rounded-lg text-sm transition-colors"
                  >
                    💓 我胸口闷，呼吸有点困难
                  </button>
                  <button
                    onClick={() => setInput('我不小心摔倒了，膝盖擦伤了')}
                    className="p-3 bg-muted hover:bg-muted/80 rounded-lg text-sm transition-colors"
                  >
                      🩹 我不小心摔倒了，膝盖擦伤了
                  </button>
                </div>
              </div>
            )}

            {/* 消息列表 */}
            {currentSession.messages.map((message) => (
              <div
                key={message.id}
                className={cn(
                  'flex',
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                )}
              >
                <div
                  className={cn(
                    'max-w-[85%] rounded-2xl px-4 py-3',
                    message.role === 'user'
                      ? 'bg-primary text-primary-foreground rounded-br-md'
                      : 'bg-muted rounded-bl-md'
                  )}
                >
                  {/* 用户消息 */}
                  {message.role === 'user' ? (
                    <div>
                      {message.image && (
                        <img
                          src={`data:image/jpeg;base64,${message.image}`}
                          alt="上传的图片"
                          className="max-w-full h-auto rounded-lg mb-2"
                        />
                      )}
                      <p className="whitespace-pre-wrap">{message.content}</p>
                      <span className="text-xs opacity-70 mt-1 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {message.timestamp.toLocaleTimeString('zh-CN', {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                  ) : (
                    // 助手消息
                    <div className="space-y-3">
                      {/* Markdown 内容 */}
                      {message.content && (
                        <div className="markdown-body prose-sm max-w-none">
                          <ReactMarkdown>{message.content}</ReactMarkdown>
                        </div>
                      )}

                      {/* 分诊结果卡片 */}
                      {message.triageData && message.triageData.triage_level && (
                        <TriageCard data={message.triageData} />
                      )}

                      {/* 医院导航卡片 */}
                      {message.triageData && message.triageData.navigation && (
                        <HospitalCard
                          navigation={message.triageData.navigation}
                          onNavigate={handleNavigate}
                        />
                      )}

                      {/* 澄清问题 */}
                      {message.triageData &&
                        message.triageData.clarify_questions.length > 0 && (
                          <div className="space-y-2">
                            <p className="text-sm font-medium">需要更多信息：</p>
                            {message.triageData.clarify_questions.map(
                              (q, idx) => (
                                <button
                                  key={idx}
                                  onClick={() => setInput(q)}
                                  className="block w-full text-left p-2 bg-background hover:bg-muted rounded text-sm transition-colors"
                                >
                                  {q}
                                </button>
                              )
                            )}
                          </div>
                        )}

                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {message.timestamp.toLocaleTimeString('zh-CN', {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* 加载状态 */}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-muted rounded-2xl rounded-bl-md px-4 py-3">
                  <div className="flex items-center gap-1">
                    <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" />
                    <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce delay-100" />
                    <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce delay-200" />
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* 免责声明 */}
        <div className="px-4 pb-2">
          <div className="max-w-3xl mx-auto">
            <Disclaimer />
          </div>
        </div>

        {/* 输入区域 */}
        <div className="p-4 border-t border-border bg-card">
          <div className="max-w-3xl mx-auto">
            {/* 图片预览 */}
            {imageData && (
              <div className="mb-2 relative inline-block">
                <img
                  src={`data:image/jpeg;base64,${imageData}`}
                  alt="预览"
                  className="h-20 rounded-lg"
                />
                <button
                  onClick={() => setImageData(null)}
                  className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white rounded-full text-xs"
                >
                  ×
                </button>
              </div>
            )}

            {/* 输入框 */}
            <div className="flex items-end gap-2">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleImageUpload}
                accept="image/jpeg,image/png"
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="p-2 hover:bg-muted rounded-lg transition-colors text-muted-foreground hover:text-foreground"
                title="上传图片"
              >
                <ImageIcon className="w-5 h-5" />
              </button>
              <button
                onClick={handleGetLocation}
                className={cn(
                  'p-2 hover:bg-muted rounded-lg transition-colors',
                  gpsLocation ? 'text-blue-500' : 'text-muted-foreground hover:text-foreground'
                )}
                title="获取位置"
              >
                <MapPin className="w-5 h-5" />
              </button>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="描述您的症状..."
                rows={1}
                className="flex-1 px-4 py-2 bg-muted rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary min-h-[44px] max-h-32"
                style={{ height: 'auto' }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement;
                  target.style.height = 'auto';
                  target.style.height = Math.min(target.scrollHeight, 128) + 'px';
                }}
              />
              <button
                onClick={handleSend}
                disabled={isLoading || (!input.trim() && !imageData)}
                className={cn(
                  'p-2 rounded-lg transition-colors',
                  isLoading || (!input.trim() && !imageData)
                    ? 'bg-muted text-muted-foreground cursor-not-allowed'
                    : 'bg-primary text-primary-foreground hover:opacity-90'
                )}
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
