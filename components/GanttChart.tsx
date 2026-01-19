import React, { useMemo, useState, useRef, useEffect } from 'react';
import { Task, ProjectData } from '../types';

interface Props {
  data: ProjectData;
}

const GanttChart: React.FC<Props> = ({ data }) => {
  // Local state to track expanded tasks (IDs)
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set());
  const [hoveredTask, setHoveredTask] = useState<{ id: string, name: string, phase: string, description?: string, duration: number, buffer?: number, type: 'TASK'|'SUBTASK' } | null>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  const toggleExpand = (taskId: string) => {
    const newSet = new Set(expandedTasks);
    if (newSet.has(taskId)) newSet.delete(taskId);
    else newSet.add(taskId);
    setExpandedTasks(newSet);
  };

  // Track mouse for floating tooltip
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  const maxHours = useMemo(() => {
    if (!data.tasks.length) return 24;
    const max = Math.max(...data.tasks.map(t => (t.startOffset || 0) + (t.duration || 0) + (t.buffer || 0)));
    return isNaN(max) ? 100 : max + 10;
  }, [data.tasks]);

  const getPhaseColor = (phase: string, isBuffer = false, opacity = 1) => {
    let hash = 0;
    for (let i = 0; i < phase.length; i++) {
      hash = phase.charCodeAt(i) + ((hash << 5) - hash);
    }
    const h = Math.abs(hash) % 360;
    return isBuffer 
      ? `hsla(${h}, 70%, 50%, 0.3)` 
      : `hsla(${h}, 70%, 60%, ${opacity})`;
  };

  const scale = 24; // Pixels per hour

  return (
    <div className="flex flex-col h-full bg-surface/30 rounded-xl overflow-hidden shadow-2xl border border-slate-700 relative" ref={containerRef}>
      
      {/* Header Info */}
      <div className="p-6 bg-surface border-b border-slate-700 shrink-0">
        <div className="flex justify-between items-start">
          <div>
            <h2 className="text-2xl font-bold text-slate-100">{data.title}</h2>
            <p className="text-slate-400 text-sm mt-1 max-w-3xl line-clamp-2">{data.description}</p>
          </div>
          <div className="text-right">
             <span className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Total Duration</span>
             <div className="text-xl font-mono text-primary">
                {isNaN(maxHours) ? '---' : Math.ceil(maxHours - 10)} Hours
             </div>
          </div>
        </div>
        
        {data.assumptions && data.assumptions.length > 0 && (
          <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-md">
            <h4 className="text-yellow-500 text-xs font-bold uppercase tracking-wide mb-1 flex items-center gap-2">
              <span>⚠️</span> Assumptions Made
            </h4>
            <ul className="text-xs text-slate-300 list-disc list-inside grid grid-cols-1 gap-y-1">
              {data.assumptions.map((a, i) => (
                <li key={i} className="whitespace-normal leading-relaxed">{a}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Gantt Scroll Area */}
      <div className="flex-1 overflow-auto gantt-scroll relative bg-background">
        <div className="inline-block min-w-full">
          <div className="flex flex-col">
            
            {/* Timeline Header */}
            <div className="flex sticky top-0 z-30 h-10 bg-slate-800 border-b border-slate-700 shadow-md">
              <div className="sticky left-0 w-64 md:w-80 bg-slate-800 border-r border-slate-700 shrink-0 flex items-center px-4 font-semibold text-xs text-slate-400 uppercase tracking-wider z-40">
                Task Name
              </div>
              <div className="relative h-full flex-1" style={{ width: `${maxHours * scale}px` }}>
                 {Array.from({ length: Math.ceil(maxHours / 5) + 1 }).map((_, i) => (
                    <div 
                      key={i} 
                      className="absolute top-0 bottom-0 border-l border-slate-700/50"
                      style={{ left: `${i * 5 * scale}px` }}
                    >
                      <span className="absolute top-2 left-1 text-[9px] text-slate-500 font-mono">
                        {i * 5}h
                      </span>
                    </div>
                 ))}
              </div>
            </div>

            {/* Task Rows */}
            <div className="flex-1 relative">
               <div className="absolute inset-0 pointer-events-none z-0">
                  {Array.from({ length: Math.ceil(maxHours / 5) + 1 }).map((_, i) => (
                    <div 
                      key={i} 
                      className="absolute top-0 bottom-0 border-l border-slate-800"
                      style={{ left: `${320 + (i * 5 * scale)}px` }}
                    />
                  ))}
               </div>

               {data.tasks.map((task) => {
                 const isExpanded = expandedTasks.has(task.id);
                 let currentSubtaskOffset = 0; // Accumulator for subtask stacking (simple sequential)

                 return (
                 <React.Fragment key={task.id}>
                   {/* PARENT TASK ROW */}
                   <div className="flex group hover:bg-slate-800/50 transition-colors h-12 border-b border-slate-800/50 relative z-10">
                      
                      {/* Left Col */}
                      <div className="sticky left-0 w-64 md:w-80 bg-surface/95 backdrop-blur border-r border-slate-700 shrink-0 flex items-center px-4 z-20 group-hover:bg-slate-800 transition-colors cursor-pointer" onClick={() => toggleExpand(task.id)}>
                         <div className="mr-2 text-slate-400 hover:text-white transition-colors">
                           {isExpanded ? '▼' : '▶'}
                         </div>
                         <div className="min-w-0 flex-1">
                            <div className="text-sm font-medium text-slate-200 truncate">{task.name}</div>
                            <div className="flex items-center gap-2">
                               <div className="text-[10px] uppercase tracking-wider truncate" style={{color: getPhaseColor(task.phase)}}>{task.phase}</div>
                               <div className="text-[9px] text-slate-500">{task.subtasks?.length || 0} items</div>
                            </div>
                         </div>
                      </div>

                      {/* Timeline Bar */}
                      <div className="relative flex-1 h-full" style={{ width: `${maxHours * scale}px` }}>
                         <div 
                            className="absolute top-2 h-8 rounded-md flex items-center shadow-md cursor-pointer hover:ring-2 ring-white/20 transition-all"
                            style={{
                              left: `${(task.startOffset || 0) * scale}px`,
                              width: `${((task.duration || 0) + (task.buffer || 0)) * scale}px`,
                            }}
                            onMouseEnter={() => setHoveredTask({ ...task, type: 'TASK' })}
                            onMouseLeave={() => setHoveredTask(null)}
                            onClick={() => toggleExpand(task.id)}
                         >
                            {/* Duration Segment */}
                            <div 
                               className="h-full rounded-l-md flex items-center px-2 overflow-hidden"
                               style={{ width: `${(task.duration / (task.duration + task.buffer)) * 100}%`, backgroundColor: getPhaseColor(task.phase) }}
                            >
                              <span className="text-[10px] font-bold text-slate-900 truncate sticky left-0">{task.duration}h</span>
                            </div>

                            {/* Buffer Segment */}
                            <div 
                               className="h-full flex-1 rounded-r-md flex items-center justify-center relative overflow-hidden"
                               style={{ backgroundColor: getPhaseColor(task.phase, true) }}
                            >
                               <div className="absolute inset-0 opacity-20" 
                                    style={{ backgroundImage: 'repeating-linear-gradient(45deg, #000, #000 5px, transparent 5px, transparent 10px)' }}>
                               </div>
                               {task.buffer > 0 && <span className="text-[9px] text-white/50 relative z-10">+{task.buffer}h</span>}
                            </div>
                         </div>
                      </div>
                   </div>

                   {/* SUBTASK ROWS (Conditional) */}
                   {isExpanded && task.subtasks && task.subtasks.map((sub, idx) => {
                      // Simple assumption: Subtasks run sequentially within the parent task duration for visualization
                      // If duration is 0, give it a min width
                      const subDuration = sub.duration || 0.5;
                      const relativeStart = currentSubtaskOffset;
                      currentSubtaskOffset += subDuration;
                      // Cap visually at parent duration to avoid overflowing if estimate was loose
                      const visualStart = (task.startOffset || 0) + relativeStart;
                      
                      return (
                        <div key={`${task.id}-sub-${idx}`} className="flex group hover:bg-slate-800/30 transition-colors h-8 border-b border-slate-800/30 relative z-10 bg-slate-900/20">
                           {/* Left Col - Indented */}
                           <div className="sticky left-0 w-64 md:w-80 bg-surface/90 backdrop-blur border-r border-slate-700 shrink-0 flex items-center px-4 pl-10 z-20 group-hover:bg-slate-800/50 transition-colors">
                              <div className="min-w-0 flex-1">
                                 <div className="text-xs text-slate-400 truncate flex items-center gap-2">
                                   <span className="w-1.5 h-1.5 rounded-full bg-slate-600"></span>
                                   {sub.name}
                                 </div>
                              </div>
                           </div>

                           {/* Timeline Bar - Subtask */}
                           <div className="relative flex-1 h-full" style={{ width: `${maxHours * scale}px` }}>
                              <div 
                                 className="absolute top-2 h-4 rounded-sm flex items-center shadow-sm cursor-help hover:brightness-110 transition-all"
                                 style={{
                                   left: `${visualStart * scale}px`,
                                   width: `${subDuration * scale}px`,
                                   backgroundColor: getPhaseColor(task.phase, false, 0.7)
                                 }}
                                 onMouseEnter={() => setHoveredTask({ 
                                    id: `${task.id}-sub-${idx}`, 
                                    name: sub.name, 
                                    phase: task.phase, 
                                    description: sub.description,
                                    duration: subDuration,
                                    type: 'SUBTASK'
                                 })}
                                 onMouseLeave={() => setHoveredTask(null)}
                              >
                              </div>
                           </div>
                        </div>
                      );
                   })}

                 </React.Fragment>
               )})}
            </div>
          </div>
        </div>
      </div>

      {/* GLOBAL TOOLTIP - Rendered at root level */}
      {hoveredTask && (
        <div 
          className="fixed z-50 pointer-events-none animate-in fade-in duration-150"
          style={{ 
             left: Math.min(mousePos.x + 15, window.innerWidth - 270), 
             top: Math.min(mousePos.y + 15, window.innerHeight - 200) 
          }}
        >
          <div className="bg-slate-800 border border-slate-600 p-4 rounded-xl shadow-2xl w-64 backdrop-blur-xl">
             <div className="flex justify-between items-center mb-1">
                <div className="text-xs font-bold uppercase" style={{ color: getPhaseColor(hoveredTask.phase) }}>{hoveredTask.type === 'SUBTASK' ? 'Subtask' : hoveredTask.phase}</div>
             </div>
             <div className="font-bold text-slate-100 text-sm mb-1">{hoveredTask.name}</div>
             <p className="text-xs text-slate-400 mb-3 line-clamp-4 leading-relaxed">{hoveredTask.description}</p>
             
             <div className="flex justify-between items-center text-xs font-mono border-t border-slate-700 pt-2">
                 <span>{hoveredTask.duration}h work</span>
                 {hoveredTask.buffer ? <span className="text-emerald-400">+{hoveredTask.buffer}h buffer</span> : null}
             </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default GanttChart;