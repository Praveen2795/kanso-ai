import { GoogleGenAI, Type, Schema } from "@google/genai";
import { Task, ProjectData, UploadedFile } from "../types";

// Helper to get client
const getClient = () => {
  const apiKey = process.env.API_KEY;
  if (!apiKey) throw new Error("API Key missing");
  return new GoogleGenAI({ apiKey });
};

// --- schemas ---

const clarificationSchema: Schema = {
  type: Type.OBJECT,
  properties: {
    needsClarification: { type: Type.BOOLEAN },
    questions: { 
      type: Type.ARRAY, 
      items: { type: Type.STRING } 
    },
    reasoning: { type: Type.STRING }
  },
  required: ["needsClarification", "reasoning"]
};

const subtaskSchema: Schema = {
  type: Type.OBJECT,
  properties: {
    name: { type: Type.STRING },
    description: { type: Type.STRING },
    duration: { type: Type.NUMBER, description: "Duration in hours" }
  },
  required: ["name", "duration"]
};

const taskSchema: Schema = {
  type: Type.OBJECT,
  properties: {
    id: { type: Type.STRING },
    name: { type: Type.STRING },
    phase: { type: Type.STRING },
    description: { type: Type.STRING },
    complexity: { type: Type.STRING, enum: ["Low", "Medium", "High"] },
    subtasks: {
      type: Type.ARRAY,
      items: subtaskSchema
    },
    dependencies: { 
      type: Type.ARRAY, 
      items: { type: Type.STRING } 
    },
    duration: { type: Type.NUMBER, description: "Total estimated hours for this task" },
    buffer: { type: Type.NUMBER, description: "Recommended buffer hours" },
    startOffset: { type: Type.NUMBER, description: "Hours from start of project" }
  },
  required: ["id", "name", "phase", "duration", "buffer", "startOffset", "complexity", "subtasks"]
};

const projectPlanSchema: Schema = {
  type: Type.OBJECT,
  properties: {
    projectTitle: { type: Type.STRING },
    projectSummary: { type: Type.STRING },
    assumptions: {
      type: Type.ARRAY,
      items: { type: Type.STRING },
      description: "List of assumptions made if user input was vague or URLs were inaccessible."
    },
    tasks: { 
      type: Type.ARRAY, 
      items: taskSchema 
    }
  },
  required: ["projectTitle", "tasks"]
};

const validationSchema: Schema = {
  type: Type.OBJECT,
  properties: {
    isValid: { type: Type.BOOLEAN },
    critique: { type: Type.STRING, description: "If invalid, provide specific instructions to the agent on what to fix." }
  },
  required: ["isValid", "critique"]
};

const chatOutputSchema: Schema = {
  type: Type.OBJECT,
  properties: {
    reply: { type: Type.STRING },
    updatedPlan: projectPlanSchema
  },
  required: ["reply"]
};

const fileRelevanceSchema: Schema = {
  type: Type.OBJECT,
  properties: {
    isRelevant: { type: Type.BOOLEAN },
    reason: { type: Type.STRING }
  },
  required: ["isRelevant", "reason"]
};

// --- Algorithms ---

// Deterministic scheduler to ensure no overlaps on dependencies
export const recalculateSchedule = (tasks: Task[]): Task[] => {
  const taskMap = new Map<string, Task>();
  tasks.forEach(t => taskMap.set(t.id, { ...t, startOffset: 0 }));

  const visited = new Set<string>();
  const visiting = new Set<string>();

  const calculateStart = (taskId: string): number => {
    if (visiting.has(taskId)) {
      console.warn("Circular dependency detected:", taskId);
      return 0; // Break cycle
    }
    if (visited.has(taskId)) {
      return taskMap.get(taskId)!.startOffset;
    }

    visiting.add(taskId);
    const task = taskMap.get(taskId);
    
    let maxDependencyEnd = 0;
    if (task && task.dependencies) {
      for (const depId of task.dependencies) {
        if (taskMap.has(depId)) {
          const depStart = calculateStart(depId);
          const depTask = taskMap.get(depId)!;
          const depEnd = depStart + (depTask.duration || 0) + (depTask.buffer || 0);
          if (depEnd > maxDependencyEnd) {
            maxDependencyEnd = depEnd;
          }
        }
      }
    }

    if (task) {
      task.startOffset = maxDependencyEnd;
    }
    
    visiting.delete(taskId);
    visited.add(taskId);
    return maxDependencyEnd;
  };

  tasks.forEach(t => calculateStart(t.id));
  return Array.from(taskMap.values()).sort((a, b) => a.startOffset - b.startOffset);
};


// --- Agents ---

export const analyzeRequest = async (topic: string, chatHistory: string[] = []) => {
  const client = getClient();
  const today = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
  
  const prompt = `
    You are the ANALYST Agent. Your goal is to deeply understand the user's project request.
    
    Current Date: ${today}
    User Topic: "${topic}"
    Previous Context: ${JSON.stringify(chatHistory)}

    1. **Verify Technical Terms**: Use Google Search to check if terms exist.
    2. **Link Detection**: If the user provided a URL, check if it's accessible via Google Search.
    3. **Identify Ambiguity**: If context is missing (skill level, deadline, scale), ask for it.
    
    Generate 2-3 **SMART** questions. If a URL was provided but seems broken or irrelevant, ask about it.
    Guardrails: Reject illegal/harmful topics.
  `;

  const response = await client.models.generateContent({
    model: "gemini-3-pro-preview",
    contents: prompt,
    config: {
      tools: [{ googleSearch: {} }],
      responseMimeType: "application/json",
      responseSchema: clarificationSchema,
    }
  });

  return JSON.parse(response.text || "{}");
};

export const checkFileRelevance = async (topic: string, file: UploadedFile) => {
  const client = getClient();
  const prompt = `
    You are a VALIDATION AGENT.
    
    User Topic: "${topic}"
    Attached File: "${file.name}"
    
    Task: Determine if the content of the attached file is RELEVANT to the User Topic.
    
    Rules:
    1. If the file contains a schedule, list, notes, diagram, or text related to "${topic}", return isRelevant: true.
    2. If the file is completely unrelated (e.g. a selfie, a meme, a receipt for coffee) and the topic is something else (e.g. "Build a website"), return isRelevant: false.
    3. If you are unsure or the connection is weak but possible, return isRelevant: true.
    
    Output JSON.
  `;

  const response = await client.models.generateContent({
    model: "gemini-3-flash-preview", // Fast model for validation
    contents: {
      parts: [
        { text: prompt },
        {
          inlineData: {
            mimeType: file.type,
            data: file.data
          }
        }
      ]
    },
    config: {
      responseMimeType: "application/json",
      responseSchema: fileRelevanceSchema
    }
  });

  return JSON.parse(response.text || "{}");
};

/**
 * ARCHITECT AGENT
 * Creates structural backbone. Accepts optional critique from Reviewer to refine output.
 */
export const createProjectStructure = async (topic: string, context: string, critique?: string, file?: UploadedFile) => {
  const client = getClient();
  const today = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
  
  let promptText = `
    You are the ARCHITECT Agent.
    Goal: Create the STRUCTURAL BACKBONE of a project plan for: "${topic}".
    Current Date: ${today}
    User Context: "${context}"
    
    ${file ? `**IMPORTANT: The user has attached a file (${file.name}). Use the visual/text information from this image/document to build the plan. Treat it as the primary source of truth for task names or schedule constraints if relevant.**` : ''}

    **Instructions:**
    1. **Research & URLs**: Use Google Search. If user provided a URL, prioritize it.
    2. **Breakdown**: Create Phases -> Tasks -> Subtasks.
       - Each Task MUST have at least 3-5 concrete subtasks.
    3. **Dependencies**: Define logical order (Task B depends on Task A).
    4. **Output**: Return the JSON structure. 
       - Set 'duration' to 0 or placeholders. The Estimator Agent will fix them later.
    
    Output pure JSON.
  `;

  if (critique) {
    promptText += `\n\n**IMPORTANT FEEDBACK FROM REVIEWER (Must Fix):**\nYour previous attempt was rejected. Fix the following issues:\n${critique}`;
  }

  // Build the parts for the model
  const parts: any[] = [{ text: promptText }];
  
  if (file) {
    parts.push({
      inlineData: {
        mimeType: file.type,
        data: file.data
      }
    });
  }

  const response = await client.models.generateContent({
    model: "gemini-3-pro-preview",
    contents: { parts },
    config: {
      tools: [{ googleSearch: {} }],
      responseMimeType: "application/json",
      responseSchema: projectPlanSchema,
      thinkingConfig: { thinkingBudget: 2048 }
    }
  });

  return JSON.parse(response.text || "{}");
};

/**
 * REVIEWER AGENT (Validation Mode)
 * Checks the Architect's structure for logical gaps before allowing Estimation.
 */
export const validateStructure = async (plan: any) => {
  const client = getClient();
  const prompt = `
    You are the REVIEWER Agent. You are quality control for the Architect.
    
    Review this project structure:
    ${JSON.stringify(plan)}

    **Checklist:**
    1. Are the dependencies logical? (e.g. You can't paint walls before building them).
    2. Are tasks missing? (e.g. "Software Project" without "Testing" phase).
    3. Are subtasks too vague?
    
    If MAJOR issues exist, set 'isValid' to false and write a SCATHING critique for the Architect to fix it.
    If minor or no issues, set 'isValid' to true.
  `;

  const response = await client.models.generateContent({
    model: "gemini-3-flash-preview",
    contents: prompt,
    config: {
      responseMimeType: "application/json",
      responseSchema: validationSchema
    }
  });

  return JSON.parse(response.text || "{}");
};

/**
 * ESTIMATOR AGENT
 * Calculates time. Accepts optional critique to re-calculate if Reviewer rejects it.
 */
export const estimateProjectTimelines = async (architectPlan: any, critique?: string) => {
  const client = getClient();
  const today = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

  let prompt = `
    You are the ESTIMATOR Agent.
    Current Date: ${today}
    
    Input: A project structure.
    ${JSON.stringify(architectPlan)}

    **Your Goal: Perform a Bottom-Up Estimation.**
    
    1. **Iterate through every single task.**
    2. **Iterate through every subtask** within that task.
    3. **Estimate Duration**: Assign a realistic duration (in hours) to EACH subtask.
       - Consider the 'complexity' level.
       - Be conservative. Things take longer than expected.
    4. **Aggregation**: The 'duration' for the parent Task MUST be the sum of its subtasks.
    5. **Buffers**: Add a 'buffer' (approx 20% of total) to the parent task.

    Return the fully updated JSON with numbers filled in.
  `;

  if (critique) {
    prompt += `\n\n**IMPORTANT FEEDBACK FROM REVIEWER (Must Fix):**\nYour previous estimates were rejected. Fix the following:\n${critique}`;
  }

  const response = await client.models.generateContent({
    model: "gemini-3-pro-preview", 
    contents: prompt,
    config: {
      responseMimeType: "application/json",
      responseSchema: projectPlanSchema,
    }
  });

  const plan = JSON.parse(response.text || "{}");
  if (plan.tasks) {
    plan.tasks = recalculateSchedule(plan.tasks);
  }
  return plan;
}

/**
 * REVIEWER AGENT (Estimation Validation Mode)
 * Checks the Estimator's math and realism.
 */
export const validateEstimates = async (plan: any) => {
  const client = getClient();
  const prompt = `
    You are the REVIEWER Agent. You are quality control for the Estimator.
    
    Review these time estimates:
    ${JSON.stringify(plan)}

    **Checklist:**
    1. Are the times realistic? (e.g. "Build entire backend" = 1 hour is IMPOSSIBLE -> Reject).
    2. Are buffers included?
    3. Is the total timeline ridiculous?
    
    If MAJOR issues exist, set 'isValid' to false and write a critique.
  `;

  const response = await client.models.generateContent({
    model: "gemini-3-flash-preview",
    contents: prompt,
    config: {
      responseMimeType: "application/json",
      responseSchema: validationSchema
    }
  });

  return JSON.parse(response.text || "{}");
};

// Final cleanup (Sanitization)
export const reviewAndRefinePlan = async (currentPlan: any) => {
  // This is the final pass to ensure JSON structure is perfect for the UI
  // It acts more like a "Formatter" now that logic is validated previously.
  const client = getClient();
  const prompt = `
    You are the FINAL REVIEWER.
    Ensure this JSON is perfectly formatted for the frontend.
    ${JSON.stringify(currentPlan)}
    
    Sanity check:
    - Ensure 'duration' is > 0 for all tasks.
    - Ensure 'dependencies' refer to real IDs.
    
    Return the clean JSON.
  `;

  const response = await client.models.generateContent({
    model: "gemini-3-flash-preview", 
    contents: prompt,
    config: {
      responseMimeType: "application/json",
      responseSchema: projectPlanSchema,
    }
  });

  const plan = JSON.parse(response.text || "{}");
  if (plan.tasks) {
    plan.tasks = recalculateSchedule(plan.tasks);
  }
  return plan;
};

export const chatWithProjectManager = async (
  currentPlan: ProjectData, 
  userMessage: string, 
  history: {role: string, content: string}[]
) => {
  const client = getClient();
  const today = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
  
  const systemInstruction = `
    You are the Project Manager Agent.
    Current Date: ${today}
    Current Project: ${JSON.stringify(currentPlan)}
    
    User Request: "${userMessage}"
    
    **Instructions:**
    1. **STRICT SCOPE & GUARDRAILS**: 
       - You are dedicated EXCLUSIVELY to refining and managing this specific project plan.
       - **DO NOT** answer general knowledge questions (e.g., "What is the capital of France?", "How do I cook pasta?", "Write a poem").
       - **DO NOT** write code or generate content unrelated to the project tasks.
       - If a user asks a generic question, politely refuse: "I'm here to help with your Gantt chart and project plan. Please ask me to modify tasks, adjust timelines, or explain the schedule."
       - IF the user asks about dangerous, illegal, sexually explicit, or hateful topics: Refuse immediately.
    
    2. **Refinement & Editing**:
       - Your primary goal is to help the user EDIT the chart.
       - If the user says "Make it shorter", "Add a marketing phase", or "Remove the buffer", you MUST return an 'updatedPlan'.
    
    3. **URL Handling**: If the user's message contains a URL, use Google Search to find information about it.
    
    4. **Task ID Persistence**: When updating the plan, you MUST preserve the existing 'id' of tasks unless deleting them. 
       
    5. **Plan Updates**: 
       - If the user asks to change the plan, return "updatedPlan" with the full JSON structure including tasks.
       - Ensure 'duration' and 'buffer' are set correctly for any modified tasks.
       - Do not recalculate start offsets manually; the system will do it. Just ensure dependencies and durations are correct.
    
    Return JSON with 'reply' and optional 'updatedPlan'.
  `;

  const response = await client.models.generateContent({
    model: "gemini-3-pro-preview", 
    contents: userMessage,
    config: {
      tools: [{ googleSearch: {} }],
      systemInstruction: systemInstruction,
      responseMimeType: "application/json",
      responseSchema: chatOutputSchema
    }
  });

  return JSON.parse(response.text || "{}");
}