import React from 'react';
import { ProjectData, Task, ComplexityLevel } from '../types';

interface Props {
  data: ProjectData;
}

const ProjectDetails: React.FC<Props> = ({ data }) => {
  const getComplexityColor = (c: ComplexityLevel) => {
    switch (c) {
      case 'High': return 'bg-red-500/20 text-red-400 border-red-500/30';
      case 'Medium': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
      case 'Low': return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
      default: return 'bg-slate-500/20 text-slate-400';
    }
  };

  return (
    <div className="h-full bg-surface/30 rounded-xl overflow-hidden shadow-2xl border border-slate-700 flex flex-col">
      <div className="p-6 border-b border-slate-700 bg-surface">
        <h2 className="text-2xl font-bold text-slate-100">Project Guide: {data.title}</h2>
        <p className="text-slate-400 mt-2">A deep dive into your tasks, subtasks, and complexity analysis.</p>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {data.tasks.map((task, index) => (
          <div key={task.id} className="bg-slate-800/50 rounded-lg border border-slate-700 p-5 hover:border-primary/50 transition-colors">
            
            {/* Header */}
            <div className="flex justify-between items-start mb-4">
              <div className="flex-1">
                 <div className="text-xs text-primary font-bold uppercase tracking-wider mb-1">{task.phase}</div>
                 <h3 className="text-xl font-bold text-white flex items-center gap-3">
                   {index + 1}. {task.name}
                   <span className={`text-[10px] px-2 py-0.5 rounded border uppercase font-bold tracking-wide ${getComplexityColor(task.complexity)}`}>
                     {task.complexity} Complexity
                   </span>
                 </h3>
              </div>
              <div className="text-right font-mono text-sm text-slate-400">
                <div>Est: {task.duration}h</div>
                <div className="text-emerald-500">Buffer: +{task.buffer}h</div>
              </div>
            </div>

            {/* Description */}
            <p className="text-slate-300 text-sm mb-6 leading-relaxed bg-slate-900/50 p-3 rounded-md border border-slate-800">
               {task.description}
            </p>

            {/* Subtasks */}
            {task.subtasks && task.subtasks.length > 0 && (
              <div>
                <h4 className="text-sm font-bold text-slate-400 uppercase tracking-wide mb-3 flex items-center gap-2">
                  <span>📋</span> Actionable Steps
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {task.subtasks.map((sub, i) => (
                    <div key={i} className="flex items-start gap-3 p-3 bg-surface rounded border border-slate-700/50">
                      <div className="w-5 h-5 rounded-full border border-slate-600 flex items-center justify-center shrink-0 mt-0.5">
                         <div className="w-2.5 h-2.5 rounded-full bg-slate-700"></div>
                      </div>
                      <div>
                        <div className="text-sm font-medium text-slate-200">{sub.name}</div>
                        {sub.description && <div className="text-xs text-slate-500 mt-1">{sub.description}</div>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default ProjectDetails;