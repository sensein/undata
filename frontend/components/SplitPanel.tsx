"use client";

import { useState, useRef, useCallback } from "react";

interface SplitPanelProps {
  leftContent: React.ReactNode;
  rightContent: React.ReactNode;
  leftLabel?: string;
  rightLabel?: string;
}

export function SplitPanel({ leftContent, rightContent, leftLabel = "Chat", rightLabel = "Editor" }: SplitPanelProps) {
  const [splitPercent, setSplitPercent] = useState(40);
  const [mobileTab, setMobileTab] = useState<"left" | "right">("left");
  const containerRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const onMouseDown = useCallback(() => { dragging.current = true; }, []);
  const onMouseUp = useCallback(() => { dragging.current = false; }, []);
  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging.current || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const pct = ((e.clientX - rect.left) / rect.width) * 100;
    setSplitPercent(Math.min(75, Math.max(25, pct)));
  }, []);

  return (
    <div className="h-[calc(100vh-80px)]">
      {/* Desktop: side-by-side */}
      <div
        ref={containerRef}
        className="hidden md:flex h-full"
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
      >
        <div style={{ width: `${splitPercent}%` }} className="overflow-auto border-r">
          {leftContent}
        </div>
        <div
          className="w-1.5 bg-gray-200 hover:bg-blue-300 cursor-col-resize flex-shrink-0"
          onMouseDown={onMouseDown}
        />
        <div style={{ width: `${100 - splitPercent}%` }} className="overflow-auto">
          {rightContent}
        </div>
      </div>

      {/* Mobile: tabs */}
      <div className="md:hidden h-full flex flex-col">
        <div className="flex border-b">
          <button
            className={`flex-1 py-2 text-sm font-medium ${mobileTab === "left" ? "border-b-2 border-blue-500 text-blue-600" : "text-gray-500"}`}
            onClick={() => setMobileTab("left")}
          >
            {leftLabel}
          </button>
          <button
            className={`flex-1 py-2 text-sm font-medium ${mobileTab === "right" ? "border-b-2 border-blue-500 text-blue-600" : "text-gray-500"}`}
            onClick={() => setMobileTab("right")}
          >
            {rightLabel}
          </button>
        </div>
        <div className="flex-1 overflow-auto">
          {mobileTab === "left" ? leftContent : rightContent}
        </div>
      </div>
    </div>
  );
}
