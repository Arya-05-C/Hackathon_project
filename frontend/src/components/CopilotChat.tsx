'use client';

import React, { useState, useRef, useEffect } from 'react';
import { 
  MessageSquare, 
  X, 
  Send, 
  Bot, 
  User, 
  Sparkles,
  Paperclip
} from 'lucide-react';
import { askCopilot } from '../lib/api';
import { ChatMessage } from '../types';
import ReactMarkdown from 'react-markdown';

interface CopilotChatProps {
  activeItemId?: string;
  activeItemName?: string;
}

export default function CopilotChat({ activeItemId, activeItemName }: CopilotChatProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: "Hello! I am your AI Procurement Copilot. I can explain supply risks, analyze inventory gaps, or compare suppliers using your pre-calculated metrics. What can I help you with today?"
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Suggestions changes based on SKU details context
  const suggestions = activeItemId 
    ? [
        `Why is ${activeItemId} priority?`,
        `Compare suppliers for ${activeItemId}`,
        `What is the stockout risk?`
      ]
    : [
        "Compare supplier archetypes",
        "Explain FOODS_2 shortages",
        "What is risk score weight?"
      ];

  // Scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const handleSend = async (textToSend: string) => {
    if (!textToSend.trim() || isLoading) return;

    const userMsg: ChatMessage = { role: 'user', content: textToSend };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      // Pass the conversation history (excluding the first greetings message)
      const historyToSend = messages.slice(1);
      const res = await askCopilot(textToSend, historyToSend, activeItemId);
      
      setMessages(prev => [...prev, { role: 'assistant', content: res.message }]);
    } catch (err) {
      console.error(err);
      setMessages(prev => [
        ...prev,
        { 
          role: 'assistant', 
          content: "I'm sorry, I encountered an issue connecting to the AI service. Running in offline fallback mode." 
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      {/* Floating Toggle Button */}
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 p-4 rounded-full bg-gradient-to-r from-indigo-600 to-blue-600 border border-indigo-400/30 text-white shadow-xl shadow-indigo-500/20 hover:scale-105 hover:rotate-3 active:scale-95 transition-all duration-300 z-50 flex items-center gap-2 group cursor-pointer"
      >
        <MessageSquare className="w-6 h-6 animate-pulse group-hover:scale-110" />
        <span className="max-w-0 overflow-hidden group-hover:max-w-[150px] transition-all duration-500 ease-out text-sm font-semibold whitespace-nowrap">
          Ask Copilot
        </span>
      </button>

      {/* Slide-out Drawer Panel */}
      <div
        className={`fixed top-0 right-0 w-[420px] h-screen bg-[#0D1322]/95 border-l border-white/5 shadow-2xl z-50 flex flex-col transition-transform duration-500 ease-in-out backdrop-blur-xl ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Drawer Header */}
        <div className="p-6 border-b border-white/5 flex justify-between items-center bg-[#131B2E]">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400 border border-indigo-500/20">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-bold text-white text-base">AI Copilot</h2>
              <span className="text-[10px] text-emerald-400 font-medium tracking-wide flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                Active Context Assistant
              </span>
            </div>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/5 transition-all cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Active Context indicator */}
        {activeItemId && (
          <div className="px-6 py-2 bg-indigo-600/10 border-b border-white/5 flex items-center justify-between text-xs text-indigo-300">
            <span className="font-medium truncate max-w-[280px]">
              Context: <strong className="text-white font-semibold">{activeItemName || activeItemId}</strong>
            </span>
            <span className="text-[10px] bg-indigo-500/20 text-indigo-200 px-1.5 py-0.5 rounded uppercase font-bold">
              Injected
            </span>
          </div>
        )}

        {/* Message Panel Area */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.map((msg, idx) => {
            const isBot = msg.role === 'assistant';
            return (
              <div
                key={idx}
                className={`flex gap-3 max-w-[85%] ${
                  isBot ? 'mr-auto' : 'ml-auto flex-row-reverse'
                }`}
              >
                <div
                  className={`w-7 h-7 rounded-lg flex items-center justify-center border shrink-0 ${
                    isBot 
                      ? 'bg-indigo-600/10 border-indigo-500/20 text-indigo-400' 
                      : 'bg-blue-600/10 border-blue-500/20 text-blue-400'
                  }`}
                >
                  {isBot ? <Bot className="w-4 h-4" /> : <User className="w-4 h-4" />}
                </div>

                <div
                  className={`p-3 rounded-2xl text-sm leading-relaxed border ${
                    isBot
                      ? 'bg-[#161D30]/60 border-white/5 text-white/90 rounded-tl-none'
                      : 'bg-indigo-600 text-white border-transparent rounded-tr-none'
                  }`}
                >
                  <div className="font-normal prose prose-invert max-w-none">
                    {isBot ? (
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    ) : (
                      <div className="whitespace-pre-line">{msg.content}</div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
          
          {isLoading && (
            <div className="flex gap-3 max-w-[85%] mr-auto">
              <div className="w-7 h-7 rounded-lg bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 animate-bounce" />
              </div>
              <div className="p-3 rounded-2xl text-sm border bg-[#161D30]/60 border-white/5 text-white/40 flex items-center gap-1.5 rounded-tl-none">
                <span>Analyzing data</span>
                <span className="flex gap-0.5 mt-1">
                  <span className="w-1 h-1 rounded-full bg-white/40 animate-bounce" />
                  <span className="w-1 h-1 rounded-full bg-white/40 animate-bounce [animation-delay:0.2s]" />
                  <span className="w-1 h-1 rounded-full bg-white/40 animate-bounce [animation-delay:0.4s]" />
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Suggestion Chips */}
        <div className="px-6 py-3 border-t border-white/5 bg-black/10 space-y-2">
          <p className="text-[10px] text-white/30 uppercase tracking-widest font-bold">
            Suggested Queries
          </p>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((sug, idx) => (
              <button
                key={idx}
                onClick={() => handleSend(sug)}
                className="text-xs bg-[#161D30] hover:bg-indigo-600/20 hover:text-indigo-300 border border-white/5 hover:border-indigo-500/20 text-white/70 px-3 py-1.5 rounded-full transition-all duration-300 text-left truncate max-w-full cursor-pointer"
              >
                {sug}
              </button>
            ))}
          </div>
        </div>

        {/* Chat Input form */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend(input);
          }}
          className="p-6 border-t border-white/5 bg-[#131B2E] flex gap-3 items-center"
        >
          <div className="flex-1 bg-[#090D17] border border-white/5 rounded-xl px-4 py-2.5 flex items-center gap-2 focus-within:border-indigo-500/50 transition-all">
            <input
              type="text"
              placeholder={activeItemId ? "Ask about this item..." : "Ask something..."}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="bg-transparent flex-1 text-sm outline-none text-white placeholder-white/30"
              disabled={isLoading}
            />
            <button
              type="button"
              className="p-1 text-white/25 hover:text-white/60 transition cursor-pointer"
              title="Attach context mapping"
            >
              <Paperclip className="w-4 h-4" />
            </button>
          </div>
          
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className={`p-3 rounded-xl flex items-center justify-center transition-all ${
              input.trim() && !isLoading
                ? 'bg-indigo-600 hover:bg-indigo-500 text-white cursor-pointer'
                : 'bg-white/5 text-white/20'
            }`}
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </>
  );
}
