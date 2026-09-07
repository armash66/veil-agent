import React from 'react';
import { Plus } from 'lucide-react';

interface NavigationProps {
  onNewTask: () => void;
  activeView: 'home' | 'chat';
  onSelectTask?: (taskText: string) => void;
}

export function Navigation({ onNewTask, activeView, onSelectTask }: NavigationProps) {
  const recentTasks = [
    { id: '1', title: 'Find laptops under ₹80K', time: 'Today' },
    { id: '2', title: 'Summarize ISRO Wikipedia', time: 'Today' },
    { id: '3', title: 'Compare wireless headphones', time: 'Yesterday' }
  ];

  return (
    <aside className="w-[220px] min-w-[220px] max-w-[240px] h-screen bg-[#F7F7F4] border-r border-[#E7E7E2] p-4 flex flex-col justify-between flex-shrink-0 select-none">
      <div className="flex flex-col gap-5">
        {/* WebVeil Identity */}
        <div className="flex items-center gap-2 px-1">
          <div className="w-[20px] h-[20px] rounded-full border-2 border-[#16A8C7] flex items-center justify-center">
            <div className="w-[6px] h-[6px] rounded-full bg-[#16A8C7]" />
          </div>
          <span className="text-[18px] font-semibold text-[#181817] tracking-tight">WebVeil</span>
        </div>

        {/* Primary Action Button */}
        <button
          onClick={onNewTask}
          className="w-full h-[40px] rounded-[10px] bg-[#181817] text-[#FFFFFF] text-[13px] font-medium px-3.5 flex items-center justify-center gap-2 hover:bg-[#30302E] transition-colors cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>New task</span>
        </button>

        {/* Navigation Sections */}
        <div className="space-y-4 text-[13px]">
          <div>
            <div className="text-[11px] font-semibold text-[#9A9A95] uppercase tracking-wider px-1 mb-2">
              Workspace
            </div>
            <div
              onClick={onNewTask}
              className={`px-2.5 py-1.5 rounded-lg font-medium cursor-pointer transition-colors ${
                activeView === 'home' ? 'bg-[#E7F6F9] text-[#168DA8]' : 'text-[#5F5F5B] hover:bg-[#EEEEEA]'
              }`}
            >
              Home
            </div>
          </div>

          <div>
            <div className="text-[11px] font-semibold text-[#9A9A95] uppercase tracking-wider px-1 mb-2">
              Recent Tasks
            </div>
            <div className="space-y-1">
              {recentTasks.map((task) => (
                <div
                  key={task.id}
                  onClick={() => onSelectTask && onSelectTask(task.title)}
                  className="px-2.5 py-1.5 rounded-lg text-[#5F5F5B] hover:bg-[#EEEEEA] truncate cursor-pointer transition-colors"
                  title={task.title}
                >
                  {task.title}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Footer Version Info */}
      <div className="px-1 text-[11px] text-[#9A9A95]">
        WebVeil v1.0 • Privacy Active
      </div>
    </aside>
  );
}
export default Navigation;
