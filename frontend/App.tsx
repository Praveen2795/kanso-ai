import React, { useState, useRef, useEffect } from 'react';
import { AppState, AgentStatus, AgentType, ProjectData, ChatMessage, Task, ViewMode, UploadedFile } from './types';
import AgentStatusDisplay from './components/AgentStatusDisplay';
import GanttChart from './components/GanttChart';
import ProjectDetails from './components/ProjectDetails';
import ImpactBackground from './components/ImpactBackground';
import { 
  wsService,
  recalculateSchedule 
} from './services/apiService';

const SUGGESTED_PROMPTS = [
  { emoji: '🚀', title: 'Startup Launch', text: 'Launch a Shopify store in 30 days' },
  { emoji: '✈️', title: 'Travel Logistics', text: 'Plan a 2-week itinerary for Japan' },
  { emoji: '🎓', title: 'Study Plan', text: '3-month study schedule for AWS certification' },
  { emoji: '🏠', title: 'Renovation', text: 'Kitchen remodel project management' }
];

const App: React.FC = () => {
  const [appState, setAppState] = useState<AppState>('IDLE');
  const [viewMode, setViewMode] = useState<ViewMode>('CHART');
  const [inputValue, setInputValue] = useState('');
  const [projectData, setProjectData] = useState<ProjectData | null>(null);
  const [clarifyingQuestions, setClarifyingQuestions] = useState<string[]>([]);
  const [clarificationAnswers, setClarificationAnswers] = useState<Record<string, string>>({});
  
  // File Upload State
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null);

  const [agentStatus, setAgentStatus] = useState<AgentStatus>({ active: false, name: AgentType.ANALYST, message: '' });
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [isChatOpen, setIsChatOpen] = useState(true);
  const [isRefining, setIsRefining] = useState(false);
  const [showDetailsPulse, setShowDetailsPulse] = useState(false);
  
  const chatEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Initialize chat visibility based on screen width
  useEffect(() => {
    if (window.innerWidth < 768) {
      setIsChatOpen(false);
    }
  }, []);

  useEffect(() => {
    if (isChatOpen) {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isChatOpen]);

  // Connect to WebSocket and set up status callback
  useEffect(() => {
    const unsubscribe = wsService.onStatus((status) => {
      setAgentStatus(status);
    });
    
    return () => unsubscribe();
  }, []);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64String = reader.result as string;
        // Strip the data:url prefix to get raw base64 for Gemini
        const base64Content = base64String.split(',')[1];
        setUploadedFile({
          name: file.name,
          type: file.type,
          data: base64Content
        });
      };
      reader.readAsDataURL(file);
    }
  };

  const handleStart = async (overrideInput?: string) => {
    const finalInput = overrideInput || inputValue;
    if (!finalInput.trim()) return;
    
    // If triggered via suggestion, update state to reflect selection
    if (overrideInput) setInputValue(overrideInput);

    setAppState('CLARIFYING');
    setUploadedFile(null); // Reset file on new start

    try {
      // Use WebSocket service for real-time status updates
      const analysis = await wsService.analyze(finalInput);

      if (analysis.needsClarification) {
        setClarifyingQuestions(analysis.questions);
        setAgentStatus({ active: false, name: AgentType.ANALYST, message: '' });
        return;
      }

      await generatePlan(finalInput, "Context implied from prompt.");
    } catch (e) {
      alert("Something went wrong with the AI. Please try again.");
      setAppState('IDLE');
    }
  };

  const handleClarificationSubmit = async () => {
    const context = Object.entries(clarificationAnswers)
      .map(([q, a]) => `Q: ${q}\nA: ${a}`)
      .join('\n');
    await generatePlan(inputValue, context);
  };

  const generatePlan = async (topic: string, context: string) => {
    setAppState('GENERATING');
    try {
      // Use WebSocket service for real-time status updates
      // The backend handles: file relevance check, architect, reviewer loops, estimator, final cleanup
      const projectData = await wsService.generate(topic, context, uploadedFile || undefined);

      // The backend already schedules tasks, but we ensure local consistency
      let finalTasks = recalculateSchedule(projectData.tasks);

      const finalProject: ProjectData = {
        title: projectData.title,
        description: projectData.description,
        assumptions: projectData.assumptions || [],
        tasks: finalTasks,
        totalDuration: projectData.totalDuration || 0 
      };

      setProjectData(finalProject);
      setAppState('READY');
      setAgentStatus({ active: false, name: AgentType.MANAGER, message: '' });
      setShowDetailsPulse(true);
      
      setMessages([{
        id: 'init',
        sender: 'ai',
        agent: AgentType.MANAGER,
        timestamp: Date.now(),
        text: projectData.assumptions?.length 
          ? `I've created your plan! I had to make a few assumptions (see chart). Please check the Details tab for the full breakdown. You can use this chat to refine the tasks, adjust timelines, or add new phases.`
          : `I've created your plan! Please check the Details tab for the full breakdown. Feel free to chat with me to refine the schedule, add more tasks, or adjust the complexity.`
      }]);
      
      if (window.innerWidth >= 768) {
        setIsChatOpen(true);
      }

    } catch (e) {
      console.error(e);
      setAppState('IDLE');
      alert("Failed to generate plan. Please try a simpler prompt.");
    }
  };

  const handleProjectUpdate = (newData: ProjectData) => {
    // 1. Recalculate Parent Durations based on subtasks
    const tasksWithUpdatedDurations = newData.tasks.map(task => {
        const subtaskSum = task.subtasks.reduce((sum, sub) => sum + (sub.duration || 0), 0);
        // If user deleted all subtasks or they equal 0, keep at least 1 hr or previous duration if manually set? 
        // Let's rely on sum, but ensure min 0.5.
        const newDuration = Math.max(subtaskSum, 0.5);
        return {
            ...task,
            duration: newDuration
        };
    });

    // 2. Recalculate Schedule (Start Offsets & Critical Path)
    const reScheduledTasks = recalculateSchedule(tasksWithUpdatedDurations);

    // 3. Update State
    setProjectData({
        ...newData,
        tasks: reScheduledTasks
    });
  };

  const handleSendMessage = async () => {
    if (!chatInput.trim() || !projectData) return;

    const newUserMsg: ChatMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text: chatInput,
      timestamp: Date.now()
    };
    setMessages(prev => [...prev, newUserMsg]);
    setChatInput('');
    setIsRefining(true);
    setAgentStatus({ active: true, name: AgentType.MANAGER, message: "Processing your request..." });

    try {
        const historyForAI = messages.map(m => ({ role: m.sender === 'user' ? 'user' : 'model', content: m.text }));
        
        // Use WebSocket service for real-time status updates
        const response = await wsService.chat(projectData, newUserMsg.text, historyForAI);
        
        if (response.updatedPlan && response.updatedPlan.tasks) {
            let updatedTasks = recalculateSchedule(response.updatedPlan.tasks);

            setProjectData({
                ...projectData,
                tasks: updatedTasks,
                assumptions: response.updatedPlan.assumptions || projectData.assumptions,
                title: response.updatedPlan.title || projectData.title,
                description: response.updatedPlan.description || projectData.description
            });
        }

        setAgentStatus({ active: false, name: AgentType.MANAGER, message: '' });
        setIsRefining(false);

        setMessages(prev => [...prev, {
            id: Date.now().toString(),
            sender: 'ai',
            agent: AgentType.MANAGER,
            text: response.reply,
            timestamp: Date.now()
        }]);

    } catch (e) {
        console.error(e);
        setIsRefining(false);
        setAgentStatus({ active: false, name: AgentType.MANAGER, message: '' });
        setMessages(prev => [...prev, {
            id: Date.now().toString(),
            sender: 'ai',
            agent: AgentType.MANAGER,
            text: "I encountered an error while updating the plan. Please try rephrasing your request.",
            timestamp: Date.now()
        }]);
    }
  };

  return (
    <div className="h-screen bg-background text-slate-100 flex flex-col font-sans overflow-hidden">
      
      {/* Navbar */}
      <nav className="h-14 border-b border-slate-800 flex items-center px-6 justify-between bg-surface/50 backdrop-blur-md z-50 shrink-0">
        <div className="flex items-center gap-2 cursor-pointer" onClick={() => setAppState('IDLE')}>
          <div className="w-8 h-8 bg-gradient-to-br from-primary to-purple-600 rounded-lg flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/20">K</div>
          <span className="font-bold text-xl tracking-tight text-slate-100">Kanso.AI</span>
        </div>
        
        {appState === 'READY' && (
           <div className="flex items-center gap-4">
              <div className="flex bg-slate-800 p-1 rounded-lg border border-slate-700">
                <button 
                  onClick={() => setViewMode('CHART')}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${viewMode === 'CHART' ? 'bg-primary text-white shadow' : 'text-slate-400 hover:text-white'}`}
                >
                  Gantt
                </button>
                <button 
                  onClick={() => {
                      setViewMode('DETAILS');
                      setShowDetailsPulse(false);
                  }}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                    viewMode === 'DETAILS' 
                      ? 'bg-primary text-white shadow' 
                      : showDetailsPulse 
                        ? 'bg-indigo-500/20 text-indigo-300 ring-1 ring-indigo-500/50 animate-pulse' 
                        : 'text-slate-400 hover:text-white'
                  }`}
                >
                  Details
                </button>
              </div>
              
              <button 
                onClick={() => setIsChatOpen(!isChatOpen)}
                className={`p-2 rounded-lg transition-all ${isChatOpen ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30' : 'bg-slate-800 text-slate-400 border border-slate-700 hover:text-white'}`}
                title={isChatOpen ? "Close Assistant" : "Open Assistant"}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
              </button>
           </div>
        )}
      </nav>

      {/* Main Content Area */}
      {appState === 'READY' && projectData ? (
        <div className="flex-1 flex overflow-hidden relative">
           
           {/* LEFT PANE: MAIN CONTENT */}
           <div className="flex-1 overflow-hidden p-4 flex flex-col min-w-0 bg-background/50 relative">
              {viewMode === 'CHART' ? (
                <GanttChart data={projectData} />
              ) : (
                <ProjectDetails data={projectData} onUpdate={handleProjectUpdate} />
              )}

              {/* OVERLAY VISUALIZATION FOR REFINEMENTS */}
              {isRefining && (
                <div className="absolute inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-8 animate-in fade-in duration-300">
                   <div className="w-full max-w-4xl bg-surface/50 rounded-3xl p-8 border border-slate-700/50 shadow-2xl">
                      <AgentStatusDisplay status={agentStatus} />
                   </div>
                </div>
              )}
           </div>

           {/* RIGHT PANE: CHAT */}
           <div className={`
              border-l border-slate-800 bg-surface flex flex-col shrink-0 shadow-2xl z-40 
              transition-all duration-300 ease-in-out
              fixed inset-0 top-14 
              md:relative md:top-auto md:inset-auto
              ${isChatOpen ? 'translate-x-0' : 'translate-x-full md:translate-x-0'}
              ${isChatOpen ? 'md:w-96' : 'md:w-0 md:border-l-0 md:overflow-hidden'}
           `}>
              <div className="flex flex-col h-full w-full overflow-hidden">
                <div className="p-4 border-b border-slate-700 bg-slate-900/50 flex items-center justify-between shrink-0">
                  <h3 className="font-bold flex items-center gap-2 text-slate-200">
                      <span className="text-xl">👷</span> Project Manager
                  </h3>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-green-400 bg-green-400/10 px-2 py-1 rounded-full border border-green-400/20">Online</span>
                    <button 
                      onClick={() => setIsChatOpen(false)}
                      className="md:hidden p-1 text-slate-400 hover:text-white"
                    >
                      ✕
                    </button>
                  </div>
                </div>
                
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {messages.map((msg) => (
                    <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'} animate-in slide-in-from-bottom-2`}>
                      <div className={`max-w-[85%] p-3 rounded-2xl text-sm leading-relaxed shadow-sm ${
                        msg.sender === 'user' ? 'bg-primary text-white rounded-br-none' : 'bg-slate-700 text-slate-200 rounded-bl-none'
                      }`}>
                        {msg.text}
                      </div>
                    </div>
                  ))}
                  {isRefining && (
                    <div className="flex justify-start animate-in fade-in">
                       <div className="bg-slate-700 text-slate-200 p-3 rounded-2xl rounded-bl-none flex items-center gap-2">
                          <span className="flex gap-1">
                             <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce"></span>
                             <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:0.2s]"></span>
                             <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:0.4s]"></span>
                          </span>
                       </div>
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>

                <div className="p-4 border-t border-slate-700 bg-slate-900/30 shrink-0">
                  <div className="flex gap-2">
                    <textarea 
                      className="flex-1 bg-background border border-slate-600 rounded-xl px-4 py-3 text-sm focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all placeholder-slate-500 resize-none min-h-[44px] max-h-32"
                      placeholder="Refine the plan..."
                      disabled={isRefining}
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          handleSendMessage();
                        }
                      }}
                      rows={1}
                      ref={(el) => {
                        if (el) {
                          el.style.height = 'auto'; 
                          el.style.height = el.scrollHeight + 'px';
                        }
                      }}
                    />
                    <button 
                      onClick={handleSendMessage} 
                      disabled={isRefining || !chatInput.trim()}
                      className={`w-10 h-10 rounded-full flex items-center justify-center transition-all shadow-lg text-white self-end mb-1 ${isRefining || !chatInput.trim() ? 'bg-slate-700 opacity-50 cursor-not-allowed' : 'bg-primary hover:bg-indigo-600 shadow-indigo-500/30'}`}
                    >
                      ↑
                    </button>
                  </div>
                </div>
              </div>
           </div>
        </div>
      ) : (
        /* IDLE / LOADING LAYOUT */
        <main className="flex-1 overflow-y-auto relative flex flex-col items-center justify-center p-4 min-h-[500px]">
          {/* Background Animation for IDLE state */}
          {appState === 'IDLE' && <ImpactBackground />}
          
          {appState === 'IDLE' && (
            <div className="w-full max-w-2xl text-center space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-700 z-10">
               <div className="space-y-4">
                 <h1 className="text-5xl md:text-6xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-400 to-emerald-400 pb-2 drop-shadow-sm">
                   Simplicity in Planning.
                 </h1>
                 <p className="text-lg md:text-xl max-w-lg mx-auto leading-relaxed text-slate-300 font-medium">
                   Enter any goal. We will analyze it, break it down, and build a realistic schedule for you.
                 </p>
               </div>

               <div className="relative group max-w-xl mx-auto z-10">
                  <div className="absolute -inset-1 bg-gradient-to-r from-primary to-secondary rounded-xl blur opacity-25 group-hover:opacity-50 transition duration-1000 group-hover:duration-200"></div>
                  <div className="relative flex bg-surface/90 backdrop-blur rounded-xl p-2 border border-slate-700 shadow-2xl">
                    <input 
                      type="text" 
                      value={inputValue}
                      onChange={(e) => setInputValue(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleStart()}
                      placeholder="What do you want to achieve?" 
                      className="flex-1 bg-transparent border-none outline-none px-4 py-3 text-slate-100 placeholder-slate-500 text-lg"
                      autoFocus
                    />
                    <button onClick={() => handleStart()} className="bg-primary hover:bg-indigo-600 text-white px-8 py-3 rounded-lg font-bold transition-all transform active:scale-95">Start</button>
                  </div>
               </div>

               <div className="max-w-xl mx-auto pt-4">
                 <p className="text-slate-500 text-xs uppercase tracking-wider font-bold mb-4">Try a robust example</p>
                 <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {SUGGESTED_PROMPTS.map((prompt, idx) => (
                      <button 
                        key={idx}
                        onClick={() => handleStart(prompt.text)}
                        className="flex items-center gap-3 p-3 rounded-lg border border-slate-800 bg-surface/80 hover:bg-surface/90 backdrop-blur hover:border-slate-600 transition-all text-left group"
                      >
                         <div className="text-xl grayscale group-hover:grayscale-0 transition-all">{prompt.emoji}</div>
                         <div>
                            <div className="text-sm font-bold text-slate-300 group-hover:text-white">{prompt.title}</div>
                            <div className="text-xs text-slate-500">{prompt.text}</div>
                         </div>
                      </button>
                    ))}
                 </div>
               </div>
            </div>
          )}
          {appState === 'CLARIFYING' && agentStatus.active && <AgentStatusDisplay status={agentStatus} />}
          {appState === 'CLARIFYING' && !agentStatus.active && clarifyingQuestions.length > 0 && (
            <div className="w-full max-w-xl bg-surface p-8 rounded-2xl border border-slate-700 shadow-2xl animate-in zoom-in duration-300">
              <h2 className="text-2xl font-bold mb-4 text-primary">Just a few details...</h2>
              <div className="space-y-5">
                {clarifyingQuestions.map((q, idx) => (
                  <div key={idx} className="space-y-2">
                    <label className="text-sm font-medium text-slate-300 block">{q}</label>
                    <input 
                      type="text" 
                      className="w-full bg-background border border-slate-700 rounded-lg p-3 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all"
                      placeholder="Your answer"
                      onChange={(e) => setClarificationAnswers(prev => ({...prev, [q]: e.target.value}))}
                    />
                  </div>
                ))}

                {/* FILE UPLOAD SECTION */}
                <div className="pt-4 border-t border-slate-700/50 mt-4">
                  <label className="text-sm font-medium text-slate-300 block mb-2 flex items-center justify-between">
                     <span>Upload Existing Plan or Reference</span>
                     <span className="text-xs text-slate-500 font-normal">(Optional)</span>
                  </label>
                  <div 
                    className="relative border-2 border-dashed border-slate-700 rounded-xl p-4 hover:border-primary/50 transition-colors bg-slate-800/30 text-center cursor-pointer group"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <input 
                      type="file" 
                      ref={fileInputRef}
                      onChange={handleFileUpload}
                      className="hidden"
                      accept="image/*,application/pdf"
                    />
                    {uploadedFile ? (
                        <div className="flex items-center justify-center gap-3">
                            <span className="text-2xl">📄</span>
                            <div className="text-left">
                                <div className="text-sm font-bold text-slate-200">{uploadedFile.name}</div>
                                <div className="text-xs text-emerald-400">Ready to analyze</div>
                            </div>
                            <button 
                                onClick={(e) => {
                                    e.stopPropagation();
                                    setUploadedFile(null);
                                }} 
                                className="ml-2 text-slate-500 hover:text-red-400"
                            >✕</button>
                        </div>
                    ) : (
                        <div className="py-2">
                            <div className="text-2xl mb-1 grayscale opacity-50 group-hover:grayscale-0 group-hover:opacity-100 transition-all">📂</div>
                            <div className="text-sm text-slate-400 font-medium">Click to upload</div>
                            <div className="text-xs text-slate-600 mt-1">Image or PDF supported</div>
                        </div>
                    )}
                  </div>
                </div>

              </div>
              <button onClick={handleClarificationSubmit} className="mt-8 w-full bg-gradient-to-r from-primary to-purple-600 py-4 rounded-xl font-bold text-lg hover:opacity-90 transition-opacity shadow-lg shadow-indigo-500/20">Generate Plan</button>
            </div>
          )}
          {appState === 'GENERATING' && <AgentStatusDisplay status={agentStatus} />}
        </main>
      )}
    </div>
  );
};

export default App;