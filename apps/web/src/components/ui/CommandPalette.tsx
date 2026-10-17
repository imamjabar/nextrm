"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { APP_NAME } from "@/config/brand";
import { SearchIcon, ChevronRightIcon, CommandIcon } from "@/components/ui/Icons";

interface PaletteItem {
  id: string;
  title: string;
  category: string;
  href: string;
  badge?: string;
  roles?: string[];
}

const COMMAND_ITEMS: PaletteItem[] = [
 {id:'work',title:'My work',category:'Relationships',href:'/workspace',roles:['RM']},
 {id:'retention',title:'Existing customers',category:'Relationships',href:'/retention',roles:['RM']},
 {id:'acquisition',title:'Acquisition · People and businesses',category:'Relationships',href:'/acquisition',roles:['RM']},
 {id:'pulse',title:'Relationship pulse',category:'Relationships',href:'/pulse',roles:['RM']},
 {id:'followups',title:'Follow-ups',category:'Relationships',href:'/follow-ups',roles:['RM']},
];

export function CommandPalette({ isOpen, onClose, role }: { isOpen: boolean; onClose: () => void; role: string }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const dialogRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const previousActiveElement = useRef<HTMLElement | null>(null);

  const filteredItems = COMMAND_ITEMS.filter(item => !item.roles || item.roles.includes(role)).filter((item) => {
    const q = query.toLowerCase();
    return item.title.toLowerCase().includes(q) || item.category.toLowerCase().includes(q) || item.id.includes(q);
  });

  // Focus preservation and restoration
  useEffect(() => {
    if (isOpen) {
      previousActiveElement.current = document.activeElement as HTMLElement;
      setTimeout(() => inputRef.current?.focus(), 50);
      setSelectedIndex(0);
    } else {
      setQuery("");
      if (previousActiveElement.current) {
        previousActiveElement.current.focus();
      }
    }
  }, [isOpen]);

  // Keep highlighted item visible via smooth auto-scroll
  useEffect(() => {
    if (isOpen && itemRefs.current[selectedIndex]) {
      itemRefs.current[selectedIndex]?.scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex, isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      if (e.key === "Tab") {
        const nodes = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('input, button, a[href], [tabindex="0"]') || []);
        const first = nodes[0], last = nodes[nodes.length-1];
        if (e.shiftKey && (document.activeElement === first || !dialogRef.current?.contains(document.activeElement))) {e.preventDefault();last?.focus();}
        else if (!e.shiftKey && document.activeElement === last) {e.preventDefault();first?.focus();}
      } else if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev < filteredItems.length - 1 ? prev + 1 : 0));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : filteredItems.length - 1));
      } else if (e.key === "Enter" && filteredItems[selectedIndex]) {
        e.preventDefault();
        router.push(filteredItems[selectedIndex].href);
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, filteredItems, selectedIndex, router, onClose]);

  if (!isOpen) return null;

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-label="Command search palette"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="fixed inset-0 bg-ink/40 z-50 flex items-start justify-center pt-20 p-4"
    >
      <div className="bg-surface border border-stroke rounded-panel max-w-xl w-full shadow-overlay overflow-hidden ">
        {/* Search Input Bar */}
        <div className="flex items-center px-4 py-3 border-b border-stroke gap-3 bg-canvas/40">
          <SearchIcon size={18} className="text-muted shrink-0" />
          <input
            ref={inputRef}
            type="search"
            role="combobox"
            aria-label="Search destinations"
            aria-expanded={isOpen}
            aria-autocomplete="list"
            aria-controls="palette-options"
            aria-activedescendant={filteredItems[selectedIndex] ? `option-${filteredItems[selectedIndex].id}` : undefined}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="Find a workspace destination…"
            className="w-full bg-transparent text-sm text-ink placeholder:text-muted focus:outline-none"
          />
          <div className="flex items-center space-x-1 text-[11px] text-muted border border-stroke px-1.5 py-0.5 rounded bg-white font-mono shrink-0">
            <span>ESC</span>
          </div>
        </div>

        {/* Results List */}
        <div
          id="palette-options"
          role="listbox"
          aria-label="Matching destinations"
          className="max-h-80 overflow-y-auto p-2 space-y-1"
        >
          {filteredItems.length === 0 ? (
            <div className="p-8 text-center text-xs text-muted" role="status">
              No matching destinations found for &ldquo;{query}&rdquo;.
            </div>
          ) : (
            filteredItems.map((item, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <button
                  key={item.id}
                  id={`option-${item.id}`}
                  role="option"
                  aria-selected={isSelected}
                  ref={(el) => { itemRefs.current[idx] = el; }}
                  onClick={() => {
                    router.push(item.href);
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-control text-left text-xs transition-colors cursor-pointer ${
                    isSelected ? "bg-primary-soft text-primary font-bold" : "text-ink hover:bg-canvas"
                  }`}
                >
                  <div className="flex items-center space-x-2.5 truncate">
                    <span className="text-[10px] uppercase font-semibold text-muted bg-canvas px-1.5 py-0.5 rounded border border-stroke/70">
                      {item.category}
                    </span>
                    <span className="truncate">{item.title}</span>
                  </div>
                  <div className="flex items-center space-x-2 shrink-0">
                    {item.badge && (
                      <span className="text-[10px] text-muted font-mono">{item.badge}</span>
                    )}
                    <ChevronRightIcon size={13} className="text-muted" />
                  </div>
                </button>
              );
            })
          )}
        </div>

        {/* Footer shortcuts helper */}
        <div className="px-4 py-2 border-t border-stroke bg-[#FAFBF8] flex items-center justify-between text-[11px] text-muted">
          <div className="flex items-center space-x-3">
            <span>↑↓ to navigate</span>
            <span>↵ to select</span>
          </div>
          <span>{APP_NAME} Quick Navigation</span>
        </div>
      </div>
    </div>
  );
}
