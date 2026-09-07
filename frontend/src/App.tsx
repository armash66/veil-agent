import React, { useState } from 'react';
import AppShell from './components/AppShell';
import HomeView from './components/HomeView';
import ChatView from './components/ChatView';

export interface ProductItem {
  title: string;
  price: string;
  spec: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  products?: ProductItem[];
  cheapestProduct?: string;
}

export type AppView = 'home' | 'chat';

export function App() {
  const [view, setView] = useState<AppView>('home');
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const handleNewTask = () => {
    setMessages([]);
    setView('home');
  };

  const handlePromptSubmit = (promptText: string) => {
    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: promptText,
    };

    let assistantReply: ChatMessage;

    if (promptText.toLowerCase().includes('laptop') || promptText.toLowerCase().includes('compare')) {
      assistantReply = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'I found three laptops matching your requirements.',
        products: [
          { title: 'Acer Aspire One', price: '₹38,990', spec: '16GB RAM' },
          { title: 'ASUS Vivobook 15', price: '₹64,990', spec: '16GB RAM' },
          { title: 'HP 15', price: '₹78,990', spec: '16GB RAM' },
        ],
        cheapestProduct: 'Acer Aspire One',
      };
    } else {
      assistantReply = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `I will assist you with "${promptText}". Privacy boundary verified — zero raw data leaves your local device.`,
      };
    }

    setMessages((prev) => [...prev, userMsg, assistantReply]);
    setView('chat');
  };

  const handleFollowUp = (followUpText: string) => {
    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: followUpText,
    };

    const assistantReply: ChatMessage = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: `Processing follow-up request: "${followUpText}".`,
    };

    setMessages((prev) => [...prev, userMsg, assistantReply]);
  };

  return (
    <AppShell activeView={view} onNewTask={handleNewTask} onSelectTask={handlePromptSubmit}>
      {view === 'home' ? (
        <HomeView onSubmitPrompt={handlePromptSubmit} />
      ) : (
        <ChatView messages={messages} onSendMessage={handleFollowUp} />
      )}
    </AppShell>
  );
}

export default App;
