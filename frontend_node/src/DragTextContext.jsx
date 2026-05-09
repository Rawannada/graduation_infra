import { createContext, useState } from "react";

export const DragTextContext = createContext();

export function DragTextProvider({ children }) {
  // نستخدم Object لتخزين نصوص مختلفة لكل نوع
  const [dragTexts, setDragTexts] = useState({
    pdf: "drag & drop your PDF here\nor\n click to browse",
    csv: "Drag & drop your CSV here\n or\n click to browse"
  });

  // دالة لتحديث نص معين فقط دون التأثير على البقية
  const updateDragText = (type, newText) => {
    setDragTexts((prev) => ({
      ...prev,
      [type]: newText,
    }));
  };

  return (
    <DragTextContext.Provider value={{ dragTexts, updateDragText }}>
      {children}
    </DragTextContext.Provider>
  );
}