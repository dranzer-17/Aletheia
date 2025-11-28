"use client"

import { useState, type MouseEvent } from "react"
import { Activity } from "lucide-react"
import { useRouter } from "next/navigation"
import { createNewsAnalysisSession } from "@/lib/analyzeNews"
import { cn } from "@/lib/utils"
import type { AnalyzableNews } from "@/types/news"

interface AnalyzeNewsButtonProps {
  news: AnalyzableNews
  className?: string
  size?: "sm" | "md"
  options?: { useWebSearch?: boolean; forcedAgents?: string[] }
}

export function AnalyzeNewsButton({ news, className, size = "md", options }: AnalyzeNewsButtonProps) {
  const router = useRouter()
  const [pending, setPending] = useState(false)
  const label = pending ? "Preparing…" : "Analyze"

  const handleClick = (event: MouseEvent<HTMLButtonElement>) => {
    event.preventDefault()
    event.stopPropagation()
    if (pending) return

    try {
      setPending(true)
      const sessionId = createNewsAnalysisSession(news, options)
      router.push(`/dashboard/analyze/${sessionId}`)
    } catch (err) {
      console.error("Unable to start analysis session", err)
      setPending(false)
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={pending}
      className={cn(
        "relative inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-60",
        // Subtle golden glass style
        "border border-amber-300/50 bg-background/40 text-amber-200",
        "backdrop-blur-md shadow-[0_10px_30px_rgba(0,0,0,0.35)]",
        "hover:bg-amber-300/15 hover:border-amber-300 hover:text-amber-100 hover:shadow-[0_0_20px_rgba(251,191,36,0.35)]",
        "active:scale-[0.97]",
        // Smaller variant
        size === "sm" && "px-3 py-1.5 text-xs",
        className
      )}
      aria-label="Analyze this news item"
    >
      <Activity className={cn("h-4 w-4", size === "sm" && "h-3.5 w-3.5")} />
      <span>{label}</span>
    </button>
  )
}

