// DragTextContext.jsx
import { createContext, useState } from "react";

export const DragTextContext = createContext();

export function DragTextProvider({ children }) {
  const [dragtext, setDragtext] = useState("Drag your file here");

  return (
    <DragTextContext.Provider value={{ dragtext, setDragtext }}>
      {children}
    </DragTextContext.Provider>
  );
}