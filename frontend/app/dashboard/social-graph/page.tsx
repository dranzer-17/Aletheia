"use client"

import { useCallback, useEffect, useState, type FormEvent } from "react"
import {
  AlertCircle,
  CalendarRange,
  ChevronDown,
  History,
  Loader2,
  RefreshCcw,
  Search,
  Share2,
  X,
} from "lucide-react"

import {
  RedditNetworkGraph,
  redditNodePalette,
} from "@/components/social-graph/RedditNetworkGraph"
import { API_ENDPOINTS } from "@/lib/config"
import { cn } from "@/lib/utils"
import type {
  GraphHistoryItem,
  RedditSocialGraphResponse,
  SelectedGraphNode,
} from "@/types/social-graph"
import type { Network } from "vis-network"
import * as DropdownMenu from "@radix-ui/react-dropdown-menu"

const RANGE_LABELS: Record<string, string> = {
  day: "Past day",
  month: "Past month",
  year: "Past year",
}

const RANGE_OPTIONS: { value: "day" | "month" | "year"; label: string }[] = [
  { value: "day", label: "Past day" },
  { value: "month", label: "Past month" },
  { value: "year", label: "Past year" },
]

export default function SocialGraphPage() {
  const [keyword, setKeyword] = useState("")
  const [timeRange, setTimeRange] = useState<"day" | "month" | "year">("day")
  const [graphData, setGraphData] = useState<RedditSocialGraphResponse | null>(null)
  const [selectedNode, setSelectedNode] = useState<SelectedGraphNode | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyItems, setHistoryItems] = useState<GraphHistoryItem[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [networkInstance, setNetworkInstance] = useState<Network | null>(null)

  useEffect(() => {
    if (typeof window !== "undefined") {
      setToken(localStorage.getItem("token"))
    }
  }, [])

  const fetchWithAuth = useCallback(
    async <T,>(url: string, options?: RequestInit): Promise<T> => {
      if (!token) {
        throw new Error("You must be logged in to query the social graph.")
      }
      const response = await fetch(url, {
        method: options?.method ?? "GET",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          ...(options?.headers || {}),
        },
        body: options?.body,
      })
      if (!response.ok) {
        const message = await response.text()
        throw new Error(message || "Failed to fetch social graph data.")
      }
      return (await response.json()) as T
    },
    [token]
  )

  const loadHistory = useCallback(
    async (withSpinner: boolean = true) => {
      if (!token) return
      if (withSpinner) setHistoryLoading(true)
      setHistoryError(null)
      try {
        const data = await fetchWithAuth<GraphHistoryItem[]>(API_ENDPOINTS.SOCIAL_GRAPH.HISTORY)
        setHistoryItems(data)
      } catch (err) {
        console.error(err)
        setHistoryError(err instanceof Error ? err.message : "Unable to load past graphs.")
      } finally {
        if (withSpinner) setHistoryLoading(false)
      }
    },
    [fetchWithAuth, token]
  )

  const runQuery = useCallback(async () => {
    setError(null)
    setLoading(true)
    setSelectedNode(null)

    try {
      const trimmedKeyword = keyword.trim()
      if (!trimmedKeyword) {
        throw new Error("Enter a keyword to search on Reddit.")
      }

      const payload = {
        keyword: trimmedKeyword,
        time_range: timeRange,
        max_posts: 20,
        max_comments: 100,
        max_users: 25,
      }

      const data = await fetchWithAuth<RedditSocialGraphResponse>(
        API_ENDPOINTS.SOCIAL_GRAPH.REDDIT,
        {
          method: "POST",
          body: JSON.stringify(payload),
        }
      )
      setGraphData(data)
      void loadHistory(false)
    } catch (err) {
      console.error(err)
      setGraphData(null)
      setError(err instanceof Error ? err.message : "Unable to fetch Reddit data.")
    } finally {
      setLoading(false)
    }
  }, [keyword, timeRange, fetchWithAuth, loadHistory])

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      await runQuery()
    },
    [runQuery]
  )

  const handleToggleHistory = useCallback(() => {
    setHistoryOpen((prev) => {
      const next = !prev
      if (next) {
        setSelectedNode(null)
        void loadHistory()
      }
      return next
    })
  }, [loadHistory])

  const handleLoadSavedGraph = useCallback(
    async (graphId: number) => {
      setLoading(true)
      setError(null)
      setSelectedNode(null)
      try {
        const data = await fetchWithAuth<RedditSocialGraphResponse>(
          API_ENDPOINTS.SOCIAL_GRAPH.GRAPH(graphId)
        )
        setGraphData(data)
        setKeyword(data.query.keyword)
        const normalizedRange =
          data.query.time_range === "day" || data.query.time_range === "month" || data.query.time_range === "year"
            ? data.query.time_range
            : "day"
        setTimeRange(normalizedRange)
        setHistoryOpen(false)
      } catch (err) {
        console.error(err)
        setError(err instanceof Error ? err.message : "Unable to load saved graph.")
      } finally {
        setLoading(false)
      }
    },
    [fetchWithAuth]
  )

  return (
    <>
      <div className="mx-auto max-w-6xl space-y-8 pb-16">
        <header className="space-y-3">
        <p className="text-xs uppercase tracking-[0.3em] text-white/40">Network intelligence</p>
        <h1 className="text-4xl font-semibold text-white">Reddit Social Graph</h1>
        <p className="max-w-3xl text-sm text-white/70">
          Visualize how Reddit users, posts, and comments connect across a topic. Enter a keyword and
          choose a rolling time window to pull up to 50 posts, 200 comments, and 50 high-activity
          accounts. The graph clusters interactions and lets you inspect any node.
        </p>
      </header>

      <section className="rounded-3xl border border-white/10 bg-linear-to-br from-white/5 via-white/2 to-transparent p-6 shadow-[0_30px_140px_rgba(7,8,25,0.45)] backdrop-blur">
        <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-[2fr_auto_auto] items-end">
          <label className="flex flex-col gap-2 text-sm font-medium text-white/80">
            Keyword
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" />
              <input
                type="text"
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                placeholder="e.g. elections, vaccine"
                className="w-full rounded-2xl border border-white/10 bg-black/30 py-3 pl-10 pr-4 text-white placeholder:text-white/30 focus:border-amber-300 focus:outline-none"
              />
            </div>
          </label>

          <div className="flex flex-col gap-2 text-sm font-medium text-white/80">
            Time range
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <button className="flex w-full items-center justify-between rounded-2xl border border-white/15 bg-black/30 px-4 py-2 text-left text-sm font-semibold text-white/80 backdrop-blur transition hover:text-white">
                  <span className="inline-flex items-center gap-2">
                    <CalendarRange className="h-4 w-4 text-white/50" />
                    {RANGE_OPTIONS.find((option) => option.value === timeRange)?.label}
                  </span>
                  <ChevronDown className="h-4 w-4 text-white/50" />
                </button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  align="end"
                  className="z-50 mt-2 min-w-[200px] overflow-hidden rounded-xl border border-(--glass-border) bg-(--glass-bg) p-1 text-white shadow-xl backdrop-blur-xl"
                >
                  <div className="pointer-events-none absolute inset-0 rounded-xl bg-linear-to-br from-foreground/5 via-transparent to-foreground/10" />
                  {RANGE_OPTIONS.map((option) => (
                    <DropdownMenu.Item
                      key={option.value}
                      onSelect={(event) => {
                        event.preventDefault()
                        setTimeRange(option.value)
                      }}
                      className={cn(
                        "relative z-10 flex select-none items-center gap-3 rounded-lg px-3 py-2.5 text-sm outline-none transition-colors hover:bg-white/5 focus:bg-white/5",
                        option.value === timeRange && "bg-white/5"
                      )}
                    >
                      {option.label}
                    </DropdownMenu.Item>
                  ))}
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
          </div>

          <button
            type="submit"
            className={cn(
              "self-end rounded-2xl px-6 py-3 text-sm font-semibold uppercase tracking-wide",
              "bg-linear-to-r from-amber-400/80 to-amber-200/80 text-black",
              "shadow-[0_15px_35px_rgba(251,191,36,0.35)] transition hover:scale-[1.01] hover:shadow-[0_20px_45px_rgba(251,191,36,0.4)]",
              "disabled:cursor-not-allowed disabled:opacity-50"
            )}
            disabled={loading}
          >
            {loading ? (
              <span className="inline-flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" /> Fetching
              </span>
            ) : (
              "Build Graph"
            )}
          </button>
        </form>

        {error && (
          <div className="mt-4 flex items-center gap-2 rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-100">
            <AlertCircle className="h-4 w-4" />
            <p>{error}</p>
          </div>
        )}

        {graphData && (
          <p className="mt-3 text-xs uppercase tracking-[0.2em] text-white/50">
            Range · {RANGE_LABELS[graphData.query.time_range] ?? graphData.query.time_range}
          </p>
        )}
      </section>

      <div className="relative">
        <RedditNetworkGraph
          data={graphData}
          onSelect={setSelectedNode}
          onNetworkReady={setNetworkInstance}
        />

        <div className="pointer-events-none absolute inset-0">
          <div className="pointer-events-auto absolute left-6 top-6 flex flex-wrap gap-3 rounded-3xl border border-white/10 bg-black/50 px-5 py-3 text-xs uppercase tracking-[0.2em] text-white/70 backdrop-blur">
            {[
              { label: "Posts", color: redditNodePalette.post },
              { label: "Comments", color: redditNodePalette.comment },
              { label: "Users", color: redditNodePalette.user },
            ].map((item) => (
              <span key={item.label} className="flex items-center gap-2">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: item.color }}
                />
                {item.label}
              </span>
            ))}
          </div>

          <button
            type="button"
            onClick={() =>
              networkInstance?.moveTo({
                position: { x: 0, y: 0 },
                scale: 1,
                animation: { duration: 600, easingFunction: "easeInOutQuad" },
              })
            }
            className="pointer-events-auto absolute right-6 top-6 inline-flex items-center gap-2 rounded-full border border-white/15 bg-black/60 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-white/70 backdrop-blur transition hover:text-white"
          >
            <RefreshCcw className="h-3.5 w-3.5" />
            Reset focus
          </button>

          {selectedNode && !historyOpen && (
            <div className="pointer-events-auto absolute bottom-6 right-6 w-full max-w-sm rounded-3xl border border-white/10 bg-black/70 p-5 text-sm text-white backdrop-blur">
              <div className="mb-3 flex items-center justify-between gap-3">
                <p className="text-xs uppercase tracking-[0.3em] text-white/50">
                  {selectedNode.type}
                </p>
                <button
                  type="button"
                  onClick={() => setSelectedNode(null)}
                  className="text-white/60 transition hover:text-white"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {selectedNode.type === "user" && "username" in selectedNode.payload && (
                <div className="space-y-2">
                  <p className="text-xl font-semibold">@{selectedNode.payload.username}</p>
                  <p>Posts authored: {selectedNode.payload.post_count}</p>
                  <p>Comments made: {selectedNode.payload.comment_count}</p>
                </div>
              )}

              {selectedNode.type === "post" && "title" in selectedNode.payload && (
                <div className="space-y-2">
                  <p className="text-lg font-semibold">{selectedNode.payload.title}</p>
                  <p className="text-white/70">u/{selectedNode.payload.author}</p>
                  <p>Score: {selectedNode.payload.score}</p>
                  <p>Comments: {selectedNode.payload.num_comments}</p>
                  <a
                    href={selectedNode.payload.permalink}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-2 text-amber-200 hover:text-amber-100"
                  >
                    View on Reddit <Share2 className="h-3 w-3" />
                  </a>
                </div>
              )}

              {selectedNode.type === "comment" && "body" in selectedNode.payload && (
                <div className="space-y-2">
                  <p className="font-semibold">Comment</p>
                  <p className="text-white/80">{selectedNode.payload.body || "[deleted]"}</p>
                  <p className="text-white/70">u/{selectedNode.payload.author}</p>
                  <p>Score: {selectedNode.payload.score}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      </div>
      <button
        type="button"
        onClick={handleToggleHistory}
        className="fixed bottom-6 right-6 z-40 flex h-12 w-12 items-center justify-center rounded-3xl border border-white/15 bg-black/70 text-white/70 shadow-[0_15px_40px_rgba(0,0,0,0.45)] backdrop-blur transition hover:text-white"
      >
        <History className="h-5 w-5" />
      </button>

      {historyOpen && (
        <div className="fixed bottom-24 right-6 z-40 flex h-[70vh] w-80 flex-col rounded-3xl border border-white/10 bg-black/85 p-5 text-sm text-white backdrop-blur">
          <div className="flex items-center justify-between">
            <p className="text-xs uppercase tracking-[0.3em] text-white/60">Past graphs</p>
            <button
              type="button"
              onClick={() => setHistoryOpen(false)}
              className="text-white/60 transition hover:text-white"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          {historyError && <p className="mt-3 text-xs text-red-300">{historyError}</p>}
          <div className="mt-4 flex-1 overflow-y-auto space-y-2">
            {historyLoading && (
              <div className="flex items-center justify-center py-6 text-white/60">
                <Loader2 className="h-4 w-4 animate-spin" />
              </div>
            )}
            {!historyLoading && historyItems.length === 0 && (
              <p className="text-xs text-white/50">No saved graphs yet.</p>
            )}
            {historyItems.map((item) => (
              <button
                key={item.graph_id}
                type="button"
                onClick={() => handleLoadSavedGraph(item.graph_id)}
                className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-left transition hover:bg-white/10"
              >
                <p className="text-sm font-semibold text-white">{item.keyword}</p>
                <p className="text-xs text-white/60">
                  {RANGE_LABELS[item.time_range] ?? item.time_range} ·{" "}
                  {new Date(item.created_at).toLocaleString()}
                </p>
              </button>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
