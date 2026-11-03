import { createContext, ReactNode, useContext, useState } from "react";
import type { BaselineResponse, EnhancedResponse, TranslateInput } from "./lib/api";

// The last real translation (request + backend response), shared by the Translate and Pipeline pages.
// `baseline` is only filled when the user asks for a comparison on the Pipeline page.
export interface LastTranslation { input: TranslateInput; enhanced: EnhancedResponse; baseline?: BaselineResponse }
type Ctx = { last: LastTranslation | null; setLast: (r: LastTranslation | null) => void };
const C = createContext<Ctx>({ last: null, setLast: () => {} });
export function StateProvider({ children }: { children: ReactNode }) {
  const [last, setLast] = useState<LastTranslation | null>(null);
  return <C.Provider value={{ last, setLast }}>{children}</C.Provider>;
}
export const useAppState = () => useContext(C);
