"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { DataSet, Network } from "vis-network/standalone"
import type { Edge as VisEdge, Node as VisNode, Options } from "vis-network"

import type {
  RedditSocialGraphResponse,
  SelectedGraphNode,
} from "@/types/social-graph"

type GraphVisNode = VisNode & {
  meta?: SelectedGraphNode
  baseColor?: string
}

type GraphVisEdge = VisEdge & {
  baseColor?: string
}

interface RedditNetworkGraphProps {
  data: RedditSocialGraphResponse | null
  onSelect?: (node: SelectedGraphNode | null) => void
  onNetworkReady?: (network: Network | null) => void
}

export const redditNodePalette: Record<string, string> = {
  post: "#7A9DD2",
  comment: "#FBB13C",
  user: "#BDC7BC",
}

export const redditEdgePalette: Record<string, string> = {
  authored: "#fde047",
  commented: "#fb923c",
  thread: "#93c5fd",
  reply: "#fb7185",
}

const BATCH_SIZE = 1

const truncate = (value: string, max = 48) =>
  value.length > max ? `${value.slice(0, max - 3)}…` : value

const hexToRgba = (hex: string, alpha = 1) => {
  const sanitized = hex.replace("#", "")
  const bigint = parseInt(sanitized, 16)
  const r = (bigint >> 16) & 255
  const g = (bigint >> 8) & 255
  const b = bigint & 255
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

export function RedditNetworkGraph({ data, onSelect, onNetworkReady }: RedditNetworkGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const networkRef = useRef<Network | null>(null)
  const nodesRef = useRef<DataSet<GraphVisNode> | null>(null)
  const edgesRef = useRef<DataSet<GraphVisEdge> | null>(null)
  const batchFrame = useRef<number | null>(null)
  const [foregroundColor, setForegroundColor] = useState("#ffffff")

  useEffect(() => {
    if (typeof window === "undefined") return
    const updateColor = () => {
      const value = getComputedStyle(document.documentElement).getPropertyValue("--foreground").trim()
      setForegroundColor(value || "#ffffff")
    }
    updateColor()
    const media = window.matchMedia("(prefers-color-scheme: dark)")
    const handler = () => updateColor()
    if (media.addEventListener) {
      media.addEventListener("change", handler)
    } else {
      media.addListener(handler)
    }
    return () => {
      if (media.removeEventListener) {
        media.removeEventListener("change", handler)
      } else {
        media.removeListener(handler)
      }
    }
  }, [])

  const networkOptions = useMemo<Options>(
    () => ({
      layout: {
        randomSeed: 42,
        improvedLayout: true,
      },
      physics: {
        stabilization: {
          enabled: true,
          iterations: 600,
        },
        barnesHut: {
          gravitationalConstant: -7500,
          centralGravity: 0.15,
          springLength: 160,
          springConstant: 0.04,
          damping: 0.65,
        },
      },
      nodes: {
        shape: "dot",
        borderWidth: 2,
        shadow: true,
        font: {
          color: "#e6e6e6",
        },
      },
      edges: {
        smooth: {
          enabled: true,
          type: "continuous",
        },
        color: "#4b5563",
      },
      interaction: {
        hover: true,
        tooltipDelay: 150,
        keyboard: false,
      },
    }),
    []
  )

  const applyHighlight = (focusedId: string | null) => {
    if (!nodesRef.current || !edgesRef.current || !networkRef.current) return
    const connected = focusedId
      ? new Set<string>([
          focusedId,
          ...(networkRef.current.getConnectedNodes(focusedId, "to") as string[]),
          ...(networkRef.current.getConnectedNodes(focusedId, "from") as string[]),
        ])
      : null

    const nodeUpdates = nodesRef.current.get().map((node) => {
      const isFocused = focusedId === node.id
      const isNeighbor = connected?.has(node.id as string) ?? false
      const hasFocus = Boolean(focusedId)
      const isActive = hasFocus && (isFocused || isNeighbor)
      const baseColor = node.baseColor || (typeof node.color === "string" ? node.color : "#94a3b8")
      const background = hasFocus
        ? hexToRgba(baseColor, isActive ? 0.98 : 0.15)
        : baseColor
      const border = hasFocus
        ? (isActive ? "#facc15" : hexToRgba(baseColor, 0.25))
        : baseColor
      return {
        id: node.id,
        borderWidth: isActive ? (isFocused ? 4 : 3) : 2,
        color: {
          background,
          border,
          highlight: {
            background: baseColor,
            border: "#facc15",
          },
          hover: {
            background: baseColor,
            border: "#facc15",
          },
        },
      }
    })

    const edgeUpdates = edgesRef.current.get().map((edge) => {
      const involvesFocused =
        !focusedId ||
        (connected?.has(edge.from as string) && connected?.has(edge.to as string))

      const baseColor = edge.baseColor ?? "#94a3b8"
      return {
        id: edge.id,
        width: involvesFocused ? (edge.width ?? 2) : 1,
        color: {
          color: involvesFocused ? baseColor : hexToRgba(baseColor, focusedId ? 0.15 : 1),
        },
      }
    })

    nodesRef.current.update(nodeUpdates)
    edgesRef.current.update(edgeUpdates)
  }

  useEffect(() => {
    if (!containerRef.current) return

    if (!data) {
      networkRef.current?.destroy()
      networkRef.current = null
      nodesRef.current = null
      edgesRef.current = null
      if (batchFrame.current) {
        cancelAnimationFrame(batchFrame.current)
        batchFrame.current = null
      }
      onSelect?.(null)
      onNetworkReady?.(null)
      return
    }

    const preparedNodes: GraphVisNode[] = []
    const preparedEdges: GraphVisEdge[] = []

    data.posts.forEach((post) => {
      const color = redditNodePalette.post
      const postLabel = truncate(post.title, 60)
      preparedNodes.push({
        id: `post:${post.id}`,
        label: postLabel,
        title: `${post.title}\nby u/${post.author} — r/${post.subreddit}`,
        color: {
          background: color,
          border: color,
          highlight: { background: color, border: "#facc15" },
          hover: { background: color, border: "#facc15" },
        },
        size: 34,
        font: {
          color: foregroundColor || "#ffffff",
          size: 12,
          face: "Inter, sans-serif",
          align: "center",
          vadjust: 32,
        },
        meta: { type: "post", payload: post },
        baseColor: color,
      })
    })

    data.comments.forEach((comment) => {
      const color = redditNodePalette.comment
      preparedNodes.push({
        id: `comment:${comment.id}`,
        label: "",
        title: `${comment.body || "[comment]"}\nby u/${comment.author}`,
        color: {
          background: color,
          border: color,
          highlight: { background: color, border: "#facc15" },
          hover: { background: color, border: "#facc15" },
        },
        size: 8,
        font: { color: "#1f1f1f", size: 11 },
        meta: { type: "comment", payload: comment },
        baseColor: color,
      })
    })

    data.users.forEach((user) => {
      const color = redditNodePalette.user
      preparedNodes.push({
        id: `user:${user.username}`,
        label: "",
        shape: "square",
        color: {
          background: color,
          border: color,
          highlight: { background: color, border: "#facc15" },
          hover: { background: color, border: "#facc15" },
        },
        size: 16,
        font: { color: "#111", size: 13 },
        meta: { type: "user", payload: user },
        baseColor: color,
      })
    })

    data.edges.forEach((edge) => {
      const color = redditEdgePalette[edge.edge_type] ?? "#94a3b8"
      preparedEdges.push({
        id: edge.id,
        from: edge.from,
        to: edge.to,
        color: { color },
        baseColor: color,
        width: edge.edge_type === "authored" ? 3.6 : 2.2,
        dashes: edge.edge_type === "reply",
        smooth: {
          enabled: true,
          type: edge.edge_type === "reply" ? "curvedCW" : "continuous",
        },
      })
    })

    const nodes = new DataSet<GraphVisNode>()
    const edges = new DataSet<GraphVisEdge>()
    nodesRef.current = nodes
    edgesRef.current = edges

    if (networkRef.current) {
      networkRef.current.destroy()
    }

    networkRef.current = new Network(containerRef.current, { nodes, edges }, networkOptions)
    onNetworkReady?.(networkRef.current)

    networkRef.current.on("click", (params) => {
      if (!params.nodes.length) {
        applyHighlight(null)
        onSelect?.(null)
        return
      }
      const nodeId = params.nodes[0] as string
      const nodeData = nodes.get(nodeId)
      applyHighlight(nodeId)
      onSelect?.(nodeData?.meta ?? null)
    })

    networkRef.current.once("stabilizationIterationsDone", () => {
      networkRef.current?.moveTo({
        scale: 0.9,
        animation: { duration: 600, easingFunction: "easeInOutQuad" },
      })
    })

    let nodeIndex = 0
    let edgeIndex = 0

    const pushBatch = () => {
      const nextNodes = preparedNodes.slice(nodeIndex, nodeIndex + BATCH_SIZE)
      const nextEdges = preparedEdges.slice(edgeIndex, edgeIndex + Math.max(1, BATCH_SIZE * 2))
      if (nextNodes.length) {
        nodes.add(nextNodes)
        nodeIndex += nextNodes.length
      }
      if (nextEdges.length) {
        edges.add(nextEdges)
        edgeIndex += nextEdges.length
      }

      if (nodeIndex < preparedNodes.length || edgeIndex < preparedEdges.length) {
        batchFrame.current = requestAnimationFrame(pushBatch)
      } else {
        networkRef.current?.stabilize()
      }
    }

    pushBatch()

    return () => {
      if (batchFrame.current) {
        cancelAnimationFrame(batchFrame.current)
        batchFrame.current = null
      }
      networkRef.current?.destroy()
      networkRef.current = null
    }
  }, [data, networkOptions, onSelect])

  return (
    <div className="relative h-[720px] w-full overflow-hidden rounded-3xl border border-white/10 bg-black/20">
      {!data && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center text-center text-sm text-white/60">
          <p className="text-base font-semibold text-white/80">No graph data yet</p>
          <p className="mt-2 max-w-md text-white/60">
            Submit a keyword and time range to build a Reddit interaction graph.
          </p>
        </div>
      )}
      <div ref={containerRef} className="h-full w-full" />
    </div>
  )
}


