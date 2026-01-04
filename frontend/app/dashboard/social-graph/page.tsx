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
        <p className="text-xs uppercase tracking-[0.3em] text-foreground/50">Network intelligence</p>
        <h1 className="text-4xl font-semibold text-foreground">Reddit Social Graph</h1>
        <p className="max-w-3xl text-sm text-foreground/70">
          Visualize how Reddit users, posts, and comments connect across a topic. Enter a keyword and
          choose a rolling time window to pull up to 50 posts, 200 comments, and 50 high-activity
          accounts. The graph clusters interactions and lets you inspect any node.
        </p>
      </header>

      <section className="rounded-3xl border border-border bg-card p-6 shadow-lg">
        <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-[2fr_auto_auto] items-end">
          <label className="flex flex-col gap-2 text-sm font-medium text-foreground">
            Keyword
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground/40" />
              <input
                type="text"
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                placeholder="e.g. elections, vaccine"
                className="w-full rounded-2xl border border-border bg-background py-3 pl-10 pr-4 text-foreground placeholder:text-foreground/40 focus:border-primary focus:outline-none"
              />
            </div>
          </label>

          <div className="flex flex-col gap-2 text-sm font-medium text-foreground">
            Time range
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <button className="flex w-full items-center justify-between rounded-2xl border border-border bg-background px-4 py-2 text-left text-sm font-semibold text-foreground transition hover:bg-foreground/5">
                  <span className="inline-flex items-center gap-2">
                    <CalendarRange className="h-4 w-4 text-foreground/50" />
                    {RANGE_OPTIONS.find((option) => option.value === timeRange)?.label}
                  </span>
                  <ChevronDown className="h-4 w-4 text-foreground/50" />
                </button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  align="end"
                  className="z-50 mt-2 min-w-[200px] overflow-hidden rounded-xl border border-border bg-card p-1 text-foreground shadow-xl"
                >
                  {RANGE_OPTIONS.map((option) => (
                    <DropdownMenu.Item
                      key={option.value}
                      onSelect={(event) => {
                        event.preventDefault()
                        setTimeRange(option.value)
                      }}
                      className={cn(
                        "relative z-10 flex select-none items-center gap-3 rounded-lg px-3 py-2.5 text-sm outline-none transition-colors hover:bg-foreground/10 focus:bg-foreground/10",
                        option.value === timeRange && "bg-foreground/10"
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
              "border border-primary/50 bg-primary/10 text-primary",
              "shadow-lg transition hover:bg-primary/20 hover:border-primary hover:shadow-[0_0_20px_rgba(10,127,255,0.35)]",
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
          <div className="mt-4 flex items-center gap-2 rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-600 dark:text-red-400">
            <AlertCircle className="h-4 w-4" />
            <p>{error}</p>
          </div>
        )}

        {graphData && (
          <p className="mt-3 text-xs uppercase tracking-[0.2em] text-foreground/50">
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
          <div className="pointer-events-auto absolute left-6 top-6 flex flex-wrap gap-3 rounded-3xl border border-border bg-card px-5 py-3 text-xs uppercase tracking-[0.2em] text-foreground shadow-lg">
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
            className="pointer-events-auto absolute right-6 top-6 inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-foreground shadow-lg transition hover:bg-foreground/10"
          >
            <RefreshCcw className="h-3.5 w-3.5" />
            Reset focus
          </button>

          {selectedNode && !historyOpen && (
            <div className="pointer-events-auto absolute bottom-6 right-6 w-full max-w-sm rounded-3xl border border-border bg-card p-5 text-sm text-foreground shadow-lg">
              <div className="mb-3 flex items-center justify-between gap-3">
                <p className="text-xs uppercase tracking-[0.3em] text-foreground/50">
                  {selectedNode.type}
                </p>
                <button
                  type="button"
                  onClick={() => setSelectedNode(null)}
                  className="text-foreground/60 transition hover:text-foreground"
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
                  <p className="text-foreground/70">u/{selectedNode.payload.author}</p>
                  <p>Score: {selectedNode.payload.score}</p>
                  <p>Comments: {selectedNode.payload.num_comments}</p>
                  <a
                    href={selectedNode.payload.permalink}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-2 text-primary hover:text-primary/80"
                  >
                    View on Reddit <Share2 className="h-3 w-3" />
                  </a>
                </div>
              )}

              {selectedNode.type === "comment" && "body" in selectedNode.payload && (
                <div className="space-y-2">
                  <p className="font-semibold">Comment</p>
                  <p className="text-foreground/80">{selectedNode.payload.body || "[deleted]"}</p>
                  <p className="text-foreground/70">u/{selectedNode.payload.author}</p>
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
        className="fixed bottom-6 right-6 z-40 flex h-12 w-12 items-center justify-center rounded-3xl border border-border bg-card text-foreground shadow-lg transition hover:bg-foreground/10"
      >
        <History className="h-5 w-5" />
      </button>

      {historyOpen && (
        <div className="fixed bottom-24 right-6 z-40 flex h-[60vh] w-80 flex-col rounded-3xl border border-border bg-card p-5 text-sm text-foreground shadow-lg">
          <div className="flex items-center justify-between">
            <p className="text-xs uppercase tracking-[0.3em] text-foreground/60">Past graphs</p>
            <button
              type="button"
              onClick={() => setHistoryOpen(false)}
              className="text-foreground/60 transition hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          {historyError && <p className="mt-3 text-xs text-red-600 dark:text-red-400">{historyError}</p>}
          <div className="mt-4 flex-1 overflow-y-auto space-y-2">
            {historyLoading && (
              <div className="flex items-center justify-center py-6 text-foreground/60">
                <Loader2 className="h-4 w-4 animate-spin" />
              </div>
            )}
            {!historyLoading && historyItems.length === 0 && (
              <p className="text-xs text-foreground/50">No saved graphs yet.</p>
            )}
            {historyItems.map((item) => (
              <button
                key={item.graph_id}
                type="button"
                onClick={() => handleLoadSavedGraph(item.graph_id)}
                className="w-full rounded-2xl border border-border bg-background px-4 py-3 text-left transition hover:bg-foreground/10"
              >
                <p className="text-sm font-semibold text-foreground">{item.keyword}</p>
                <p className="text-xs text-foreground/60">
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
