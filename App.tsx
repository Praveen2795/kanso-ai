import React, { useState, useRef, useEffect } from 'react';
import { AppState, AgentStatus, AgentType, ProjectData, ChatMessage, Task, ViewMode } from './types';
import AgentStatusDisplay from './components/AgentStatusDisplay';
import GanttChart from './components/GanttChart';
import ProjectDetails from './components/ProjectDetails';
import { analyzeRequest, createProjectStructure, estimateProjectTimelines, reviewAndRefinePlan, chatWithProjectManager, recalculateSchedule } from './services/geminiService';

const App: React.FC = () => {
  const [appState, setAppState] = useState<AppState>('IDLE');
  const [viewMode, setViewMode] = useState<ViewMode>('CHART');
  const [inputValue, setInputValue] = useState('');
  const [projectData, setProjectData] = useState<ProjectData | null>(null);
  const [clarifyingQuestions, setClarifyingQuestions] = useState<string[]>([]);
  const [clarificationAnswers, setClarificationAnswers] = useState<Record<string, string>>({});
  
  const [agentStatus, setAgentStatus] = useState<AgentStatus>({ active: false, name: AgentType.ANALYST, message: '' });
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const runAgent = async (name: AgentType, message: string, action: () => Promise<any>) => {
    setAgentStatus({ active: true, name, message });
    try {
      const result = await action();
      return result;
    } catch (error) {
      console.error(error);
      setAgentStatus({ active: true, name, message: "Error encountered. Retrying..." });
      throw error;
    }
  };

  const handleStart = async () => {
    if (!inputValue.trim()) return;
    setAppState('CLARIFYING');

    try {
      const analysis = await runAgent(
        AgentType.ANALYST, 
        "Analyzing project scope, verifying terms, and identifying gaps...",
        () => analyzeRequest(inputValue)
      );

      if (analysis.needsClarification) {
        setClarifyingQuestions(analysis.questions);
        setAgentStatus({ active: false, name: AgentType.ANALYST, message: '' });
        return;
      }

      await generatePlan(inputValue, "Context implied from prompt.");
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
      // 1. ARCHITECT: Structure only
      const structuralPlan = await runAgent(
        AgentType.ARCHITECT,
        "Researching real-world workflows and designing the project structure (Phases, Tasks, Subtasks)...",
        () => createProjectStructure(topic, context)
      );

      // 2. ESTIMATOR: Bottom-up estimation
      const estimatedPlan = await runAgent(
        AgentType.ESTIMATOR,
        "Calculating realistic bottom-up estimates for every single subtask and adding safety buffers...",
        () => estimateProjectTimelines(structuralPlan)
      );

      // 3. REVIEWER: Final sanity check
      const refinedPlanRaw = await runAgent(
        AgentType.REVIEWER,
        "Reviewing logic, ensuring dependencies cascade correctly, and finalizing the schedule...",
        () => reviewAndRefinePlan(estimatedPlan)
      );

      // Strict Parsing & Recalculation
      let finalTasks: Task[] = refinedPlanRaw.tasks.map((t: any) => ({
        id: t.id,
        name: t.name,
        phase: t.phase,
        startOffset: Number(t.startOffsetHours) || 0,
        duration: Math.max(Number(t.estimatedHours) || 1, 0.5),
        buffer: Number(t.recommendedBufferHours) || 0,
        dependencies: t.dependencies || [],
        description: t.description,
        complexity: t.complexity || "Medium",
        subtasks: (t.subtasks || []).map((st: any) => ({
            name: st.name,
            description: st.description,
            duration: Number(st.duration) || 0.5 
        }))
      }));

      // ENFORCE DEPENDENCIES VIA ALGORITHM
      finalTasks = recalculateSchedule(finalTasks);

      const finalProject: ProjectData = {
        title: refinedPlanRaw.projectTitle,
        description: refinedPlanRaw.projectSummary,
        assumptions: refinedPlanRaw.assumptions || [],
        tasks: finalTasks,
        totalDuration: 0 
      };

      setProjectData(finalProject);
      setAppState('READY');
      setAgentStatus({ active: false, name: AgentType.MANAGER, message: '' });
      
      setMessages([{
        id: 'init',
        sender: 'ai',
        agent: AgentType.MANAGER,
        timestamp: Date.now(),
        text: refinedPlanRaw.assumptions?.length 
          ? `I've created your plan! Since some details were missing, I made a few assumptions (see chart). You can check the "Details" tab for a deep dive.`
          : `I've created your plan! Check the "Details" tab to see subtasks and complexity analysis.`
      }]);

    } catch (e) {
      console.error(e);
      setAppState('IDLE');
      alert("Failed to generate plan. Please check API key or try a simpler prompt.");
    }
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
    setMessages(prev => [...prev, { id: 'thinking', sender: 'ai', text: '...', timestamp: Date.now() }]);

    try {
        const historyForAI = messages.map(m => ({ role: m.sender === 'user' ? 'user' : 'model', content: m.text }));
        const response = await chatWithProjectManager(projectData, newUserMsg.text, historyForAI);
        
        setMessages(prev => prev.filter(m => m.id !== 'thinking'));

        if (response.updatedPlan && response.updatedPlan.tasks) {
           let updatedTasks: Task[] = response.updatedPlan.tasks.map((t: any) => ({
                id: t.id,
                name: t.name,
                phase: t.phase,
                startOffset: Number(t.startOffsetHours) || 0,
                duration: Math.max(Number(t.estimatedHours) || 1, 0.5),
                buffer: Number(t.recommendedBufferHours) || 0,
                dependencies: t.dependencies || [],
                description: t.description,
                complexity: t.complexity || "Medium",
                subtasks: (t.subtasks || []).map((st: any) => ({
                    name: st.name,
                    description: st.description,
                    duration: Number(st.duration) || 0.5
                }))
            }));
            
            // Re-enforce dependencies on update
            updatedTasks = recalculateSchedule(updatedTasks);

            setProjectData({
                ...projectData,
                tasks: updatedTasks,
                assumptions: response.updatedPlan.assumptions || projectData.assumptions,
                title: response.updatedPlan.projectTitle || projectData.title
            });
        }

        setMessages(prev => [...prev, {
            id: Date.now().toString(),
            sender: 'ai',
            agent: AgentType.MANAGER,
            text: response.reply,
            timestamp: Date.now()
        }]);

    } catch (e) {
        console.error(e);
        setMessages(prev => prev.filter(m => m.id !== 'thinking'));
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
           <div className="flex bg-slate-800 p-1 rounded-lg border border-slate-700">
              <button 
                onClick={() => setViewMode('CHART')}
                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${viewMode === 'CHART' ? 'bg-primary text-white shadow' : 'text-slate-400 hover:text-white'}`}
              >
                Gantt Chart
              </button>
              <button 
                onClick={() => setViewMode('DETAILS')}
                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${viewMode === 'DETAILS' ? 'bg-primary text-white shadow' : 'text-slate-400 hover:text-white'}`}
              >
                Deep Details
              </button>
           </div>
        )}
      </nav>

      {/* Main Content Area */}
      {appState === 'READY' && projectData ? (
        <div className="flex-1 flex overflow-hidden">
           
           {/* LEFT PANE: MAIN CONTENT */}
           <div className="flex-1 overflow-hidden p-4 flex flex-col min-w-0 bg-background/50">
              {viewMode === 'CHART' ? (
                <GanttChart data={projectData} />
              ) : (
                <ProjectDetails data={projectData} />
              )}
           </div>

           {/* RIGHT PANE: CHAT */}
           <div className="w-96 border-l border-slate-800 bg-surface flex flex-col shrink-0 shadow-2xl z-10">
              <div className="p-4 border-b border-slate-700 bg-slate-900/50 flex items-center justify-between">
                 <h3 className="font-bold flex items-center gap-2 text-slate-200">
                    <span className="text-xl">👷</span> Project Manager
                 </h3>
                 <span className="text-xs text-green-400 bg-green-400/10 px-2 py-1 rounded-full border border-green-400/20">Online</span>
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
                <div ref={chatEndRef} />
              </div>

              <div className="p-4 border-t border-slate-700 bg-slate-900/30">
                <div className="flex gap-2">
                  <textarea 
                    className="flex-1 bg-background border border-slate-600 rounded-xl px-4 py-3 text-sm focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all placeholder-slate-500 resize-none min-h-[44px] max-h-32"
                    placeholder="Ask to change tasks, times..."
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage();
                      }
                    }}
                    rows={1}
                    style={{ height: 'auto', overflow: 'hidden' }}
                    // Auto-resize logic
                    ref={(el) => {
                      if (el) {
                        el.style.height = 'auto'; 
                        el.style.height = el.scrollHeight + 'px';
                      }
                    }}
                  />
                  <button onClick={handleSendMessage} className="w-10 h-10 bg-primary rounded-full flex items-center justify-center hover:bg-indigo-600 transition-colors shadow-lg shadow-indigo-500/30 text-white self-end mb-1">↑</button>
                </div>
              </div>
           </div>
        </div>
      ) : (
        /* IDLE / LOADING LAYOUT */
        <main className="flex-1 overflow-y-auto relative flex flex-col items-center justify-center p-4 min-h-[500px]">
          {appState === 'IDLE' && (
            <div className="w-full max-w-2xl text-center space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-700">
               <div className="space-y-4">
                 <h1 className="text-5xl md:text-6xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-400 to-emerald-400 pb-2">
                   Simplicity in Planning.
                 </h1>
                 <p className="text-lg md:text-xl max-w-lg mx-auto leading-relaxed bg-gradient-to-r from-indigo-400 via-purple-400 to-emerald-400 text-transparent bg-clip-text animate-gradient-flow font-medium">
                   Enter any goal. Our AI agents will distill it into a clear, actionable path with realistic timelines.
                 </p>
               </div>
               <div className="relative group max-w-xl mx-auto">
                  <div className="absolute -inset-1 bg-gradient-to-r from-primary to-secondary rounded-xl blur opacity-25 group-hover:opacity-50 transition duration-1000 group-hover:duration-200"></div>
                  <div className="relative flex bg-surface rounded-xl p-2 border border-slate-700 shadow-2xl">
                    <input 
                      type="text" 
                      value={inputValue}
                      onChange={(e) => setInputValue(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleStart()}
                      placeholder="e.g. Plan a surprise party, Learn Python..." 
                      className="flex-1 bg-transparent border-none outline-none px-4 py-3 text-slate-100 placeholder-slate-500 text-lg"
                      autoFocus
                    />
                    <button onClick={handleStart} className="bg-primary hover:bg-indigo-600 text-white px-8 py-3 rounded-lg font-bold transition-all transform active:scale-95">Start</button>
                  </div>
               </div>
            </div>
          )}
          {appState === 'CLARIFYING' && agentStatus.active && <AgentStatusDisplay status={agentStatus} />}
          {appState === 'CLARIFYING' && !agentStatus.active && clarifyingQuestions.length > 0 && (
            <div className="w-full max-w-xl bg-surface p-8 rounded-2xl border border-slate-700 shadow-2xl animate-in zoom-in duration-300">
              <h2 className="text-2xl font-bold mb-4 text-primary">Just a few details...</h2>
              <p className="text-slate-400 mb-6">To build the perfect chart, I need to know a bit more. If you're unsure, just leave it blank and I'll make reasonable assumptions.</p>
              <div className="space-y-5">
                {clarifyingQuestions.map((q, idx) => (
                  <div key={idx} className="space-y-2">
                    <label className="text-sm font-medium text-slate-300 block">{q}</label>
                    <input 
                      type="text" 
                      className="w-full bg-background border border-slate-700 rounded-lg p-3 focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all"
                      placeholder="Optional"
                      onChange={(e) => setClarificationAnswers(prev => ({...prev, [q]: e.target.value}))}
                    />
                  </div>
                ))}
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