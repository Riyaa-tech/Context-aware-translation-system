import { createContext, ReactNode, useContext, useState } from "react";
import type { CompareResponse } from "./lib/api";

// The last real comparison result, shared by the Translate and Pipeline pages.
type Ctx = { last: CompareResponse | null; setLast: (r: CompareResponse | null) => void };
const C = createContext<Ctx>({ last: null, setLast: () => {} });
export function StateProvider({ children }: { children: ReactNode }) {
  const [last, setLast] = useState<CompareResponse | null>(null);
  return <C.Provider value={{ last, setLast }}>{children}</C.Provider>;
}
export const useAppState = () => useContext(C);
