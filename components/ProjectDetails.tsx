import React from 'react';
import { ProjectData, Task, ComplexityLevel } from '../types';

interface Props {
  data: ProjectData;
  onUpdate: (newData: ProjectData) => void;
}

const ProjectDetails: React.FC<Props> = ({ data, onUpdate }) => {

  const handleTaskChange = (taskId: string, field: keyof Task, value: any) => {
    const newData = { ...data };
    const taskIndex = newData.tasks.findIndex(t => t.id === taskId);
    if (taskIndex !== -1) {
      newData.tasks[taskIndex] = { ...newData.tasks[taskIndex], [field]: value };
      onUpdate(newData);
    }
  };

  const handleSubtaskChange = (taskId: string, subtaskIndex: number, field: 'name' | 'description', value: string) => {
    const newData = { ...data };
    const task = newData.tasks.find(t => t.id === taskId);
    if (task && task.subtasks) {
      task.subtasks[subtaskIndex] = { ...task.subtasks[subtaskIndex], [field]: value };
      onUpdate(newData);
    }
  };

  const addSubtask = (taskId: string) => {
    const newData = { ...data };
    const task = newData.tasks.find(t => t.id === taskId);
    if (task) {
      task.subtasks.push({ name: "New Action Step", description: "Details for this step...", duration: 1 });
      onUpdate(newData);
    }
  };

  const deleteSubtask = (taskId: string, subtaskIndex: number) => {
    const newData = { ...data };
    const task = newData.tasks.find(t => t.id === taskId);
    if (task) {
      task.subtasks.splice(subtaskIndex, 1);
      onUpdate(newData);
    }
  };

  const getComplexityColor = (c: ComplexityLevel) => {
    switch (c) {
      case 'High': return 'text-red-400 border-red-500/30 bg-red-500/10';
      case 'Medium': return 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10';
      case 'Low': return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10';
      default: return 'text-slate-400 border-slate-500/30';
    }
  };

  return (
    <div className="h-full bg-surface/30 rounded-xl overflow-hidden shadow-2xl border border-slate-700 flex flex-col">
      <div className="p-6 border-b border-slate-700 bg-surface">
        <h2 className="text-2xl font-bold text-slate-100">Project Guide: {data.title}</h2>
        <p className="text-slate-400 mt-2">Edit your tasks, refine complexity, and manage detailed steps below. Changes update the chart automatically.</p>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {data.tasks.map((task, index) => (
          <div key={task.id} className="bg-slate-800/50 rounded-lg border border-slate-700 p-5 hover:border-primary/50 transition-colors group">
            
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start gap-4 mb-4">
              <div className="flex-1 w-full">
                 <div className="text-xs text-primary font-bold uppercase tracking-wider mb-1 flex justify-between">
                    <span>{task.phase}</span>
                 </div>
                 
                 <div className="flex items-start gap-2 w-full">
                   <span className="text-xl font-bold text-slate-400 mt-1">{index + 1}.</span>
                   <input 
                      type="text"
                      value={task.name}
                      onChange={(e) => handleTaskChange(task.id, 'name', e.target.value)}
                      className="flex-1 bg-transparent text-xl font-bold text-white border-b border-transparent focus:border-primary hover:border-slate-700 outline-none transition-all px-1"
                   />
                 </div>
              </div>
              
              <div className="flex flex-row md:flex-col items-end gap-2 shrink-0">
                 {/* Complexity Dropdown */}
                 <select 
                    value={task.complexity}
                    onChange={(e) => handleTaskChange(task.id, 'complexity', e.target.value)}
                    className={`text-[10px] px-2 py-1 rounded border uppercase font-bold tracking-wide outline-none cursor-pointer appearance-none ${getComplexityColor(task.complexity)}`}
                 >
                    <option value="Low" className="bg-slate-800 text-emerald-400">Low Complexity</option>
                    <option value="Medium" className="bg-slate-800 text-yellow-400">Medium Complexity</option>
                    <option value="High" className="bg-slate-800 text-red-400">High Complexity</option>
                 </select>

                 <div className="text-right font-mono text-sm text-slate-400">
                    <div>Est: {task.duration}h</div>
                 </div>
              </div>
            </div>

            {/* Description */}
            <textarea
               value={task.description || ''}
               onChange={(e) => handleTaskChange(task.id, 'description', e.target.value)}
               className="w-full text-slate-300 text-sm mb-6 leading-relaxed bg-slate-900/30 hover:bg-slate-900/50 p-3 rounded-md border border-slate-800/50 focus:border-slate-600 outline-none resize-none min-h-[80px]"
            />

            {/* Subtasks */}
            <div>
                <h4 className="text-sm font-bold text-slate-400 uppercase tracking-wide mb-3 flex items-center justify-between">
                  <span className="flex items-center gap-2">📋 Actionable Steps</span>
                </h4>
                
                <div className="grid grid-cols-1 gap-3">
                  {task.subtasks.map((sub, i) => (
                    <div key={i} className="flex items-start gap-3 p-3 bg-surface rounded border border-slate-700/50 hover:border-slate-600 group/sub">
                      <div className="w-5 h-5 rounded-full border border-slate-600 flex items-center justify-center shrink-0 mt-2">
                         <div className="w-2.5 h-2.5 rounded-full bg-slate-700"></div>
                      </div>
                      
                      <div className="flex-1 space-y-1">
                        <input 
                           type="text"
                           value={sub.name}
                           onChange={(e) => handleSubtaskChange(task.id, i, 'name', e.target.value)}
                           className="w-full bg-transparent text-sm font-medium text-slate-200 border-b border-transparent focus:border-slate-600 outline-none"
                           placeholder="Step name"
                        />
                        <input 
                           type="text"
                           value={sub.description || ''}
                           onChange={(e) => handleSubtaskChange(task.id, i, 'description', e.target.value)}
                           className="w-full bg-transparent text-xs text-slate-500 border-b border-transparent focus:border-slate-600 outline-none"
                           placeholder="Description..."
                        />
                      </div>

                      <button 
                        onClick={() => deleteSubtask(task.id, i)}
                        className="opacity-0 group-hover/sub:opacity-100 text-slate-600 hover:text-red-400 p-1 transition-all"
                        title="Remove step"
                      >
                        ✕
                      </button>
                    </div>
                  ))}

                  <button 
                    onClick={() => addSubtask(task.id)}
                    className="flex items-center justify-center gap-2 p-3 rounded border border-dashed border-slate-700 text-slate-500 hover:text-primary hover:border-primary/50 hover:bg-slate-800/50 transition-all text-sm font-medium"
                  >
                    + Add Action Step
                  </button>
                </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ProjectDetails;