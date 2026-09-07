import React, { useState } from 'react';
import Header from './Header';
import Navigation from './Navigation';

interface AppShellProps {
  children: React.ReactNode;
  activeView: 'home' | 'chat';
  onNewTask: () => void;
  onSelectTask?: (taskText: string) => void;
}

export function AppShell({ children, activeView, onNewTask, onSelectTask }: AppShellProps) {
  return (
    <div className="w-screen h-screen min-h-screen bg-[#FAFAF8] text-[#181817] flex overflow-hidden font-sans">
      {/* 1. Left Navigation (220px) */}
      <Navigation onNewTask={onNewTask} activeView={activeView} onSelectTask={onSelectTask} />

      {/* 2. Main Work Area */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        <Header />
        <main className="flex-1 overflow-hidden">
          {children}
        </main>
      </div>
    </div>
  );
}
export default AppShell;
