export enum AgentType {
  ANALYST = 'Analyst',
  ARCHITECT = 'Architect',
  ESTIMATOR = 'Estimator',
  REVIEWER = 'Reviewer',
  MANAGER = 'Manager' // For chat
}

export type ComplexityLevel = 'Low' | 'Medium' | 'High';

export interface Subtask {
  name: string;
  description?: string;
  duration: number; // Hours
}

export interface Task {
  id: string;
  name: string;
  phase: string;
  startOffset: number; // Hours from project start
  duration: number; // Estimated hours (sum of subtasks usually)
  buffer: number; // Buffer hours
  dependencies: string[]; // IDs of parent tasks
  description?: string;
  complexity: ComplexityLevel;
  subtasks: Subtask[];
  isExpanded?: boolean; // UI state for Gantt
}

export interface ProjectData {
  title: string;
  description: string;
  assumptions?: string[]; // List of assumptions made by the AI
  tasks: Task[];
  totalDuration: number;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'ai';
  text: string;
  agent?: AgentType;
  timestamp: number;
}

export type AppState = 'IDLE' | 'CLARIFYING' | 'GENERATING' | 'READY';
export type ViewMode = 'CHART' | 'DETAILS';

export interface AgentStatus {
  active: boolean;
  name: AgentType;
  message: string;
}