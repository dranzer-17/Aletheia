"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";
import {
  ChevronDown,
  Search,
  Filter,
  ArrowUpRight,
  MessageSquare,
  TrendingUp,
  Calendar,
  Loader2,
  RefreshCw,
  Check,
  ExternalLink,
} from "lucide-react";
import { API_ENDPOINTS } from "@/lib/config";
import { cn } from "@/lib/utils";
import { AnalyzeNewsButton } from "@/components/AnalyzeNewsButton";
import type { AnalyzableNews } from "@/types/news";

interface TrendItem {
  title: string;
  description: string;
  url: string;
  source: string;
  score: number;
  upvote_ratio?: number;
  num_comments: number;
  created_utc: string;
  author?: string;
  flair?: string;
  is_nsfw: boolean;
  engagement_score: number;
}

interface TrendResponse {
  platform: string;
  fetch_timestamp: string;
  update_frequency_minutes: number;
  trends: TrendItem[];
  expires_at: string;
  is_cached: boolean;
}

type Platform = "reddit" | "twitter" | "telegram" | "instagram" | "news" | "youtube";
type SortBy = "score" | "comments" | "engagement_score" | "timestamp";
type SortOrder = "asc" | "desc";

export default function TrendsPage() {
  const [selectedPlatform, setSelectedPlatform] = useState<Platform>("reddit");
  const [trends, setTrends] = useState<TrendItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastFetch, setLastFetch] = useState<string | null>(null);
  const [isCached, setIsCached] = useState(false);

  // Filters
  const [keyword, setKeyword] = useState("");
  const [sortBy, setSortBy] = useState<SortBy>("engagement_score");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [showFilters, setShowFilters] = useState(false);

  const token = useMemo(() => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("token");
  }, []);

  const fetchTrends = useCallback(
    async (platform: Platform, forceRefresh: boolean = false) => {
      if (!token) {
        setError("You must be logged in to view trends.");
        return;
      }

      setLoading(true);
      setError(null);

      try {
        let url = "";
        if (platform === "reddit") {
          url = `${API_ENDPOINTS.TRENDS.REDDIT}?force_refresh=${forceRefresh}`;
        } else if (platform === "news") {
          url = `${API_ENDPOINTS.TRENDS.NEWS}?force_refresh=${forceRefresh}`;
        } else if (platform === "telegram") {
          url = `${API_ENDPOINTS.TRENDS.TELEGRAM}?force_refresh=${forceRefresh}`;
        } else {
          // Placeholder for other platforms
          setError(`${platform} trends not yet implemented`);
          setLoading(false);
          return;
        }

        const response = await fetch(url, {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        });

        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.detail || `Failed to fetch ${platform} trends`);
        }

        const data: TrendResponse = await response.json();
        setTrends(data.trends);
        setLastFetch(data.fetch_timestamp);
        setIsCached(data.is_cached);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch trends");
      } finally {
        setLoading(false);
      }
    },
    [token]
  );

  useEffect(() => {
    if (selectedPlatform) {
      // Run async without blocking
      fetchTrends(selectedPlatform).catch(console.error);
    }
  }, [selectedPlatform, fetchTrends]);

  // Filter and sort trends - useMemo is already non-blocking
  const filteredAndSortedTrends = useMemo(() => {
    let filtered = [...trends];

    // Keyword filter
    if (keyword.trim()) {
      const keywordLower = keyword.toLowerCase();
      filtered = filtered.filter(
        (item) =>
          item.title.toLowerCase().includes(keywordLower) ||
          item.description.toLowerCase().includes(keywordLower) ||
          item.source.toLowerCase().includes(keywordLower)
      );
    }

    // Sort
    filtered.sort((a, b) => {
      let aVal: number;
      let bVal: number;

      switch (sortBy) {
        case "score":
          aVal = a.score;
          bVal = b.score;
          break;
        case "comments":
          aVal = a.num_comments;
          bVal = b.num_comments;
          break;
        case "engagement_score":
          aVal = a.engagement_score;
          bVal = b.engagement_score;
          break;
        case "timestamp":
          aVal = new Date(a.created_utc).getTime();
          bVal = new Date(b.created_utc).getTime();
          break;
        default:
          aVal = a.engagement_score;
          bVal = b.engagement_score;
      }

      return sortOrder === "asc" ? aVal - bVal : bVal - aVal;
    });

    // Return top 10 only
    return filtered.slice(0, 10);
  }, [trends, keyword, sortBy, sortOrder]);

  const formatDate = useCallback((dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  }, []);

  const formatNumber = useCallback((num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}k`;
    return num.toString();
  }, []);

  const platforms: { value: Platform; label: string; disabled?: boolean }[] = [
    { value: "reddit", label: "Reddit" },
    { value: "telegram", label: "Telegram" },
    { value: "news", label: "News" },
    { value: "twitter", label: "Twitter", disabled: true },
    { value: "instagram", label: "Instagram", disabled: true },
    { value: "youtube", label: "YouTube", disabled: true },
  ];

  const sortOptions: { value: SortBy; label: string }[] = [
    { value: "engagement_score", label: "Engagement" },
    { value: "score", label: "Score" },
    { value: "comments", label: "Comments" },
    { value: "timestamp", label: "Newest" },
  ];

  const handleRefresh = useCallback(async () => {
    await fetchTrends(selectedPlatform, true);
  }, [selectedPlatform, fetchTrends]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Live Trends</h1>
          <p className="text-sm text-foreground/60 mt-1">
            Top trending topics across social platforms
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastFetch && (
            <div className="text-xs text-foreground/50 flex items-center gap-2">
              <Calendar className="w-3.5 h-3.5" />
              <span>Updated {lastFetch ? new Date(lastFetch).toLocaleTimeString() : ""}</span>
              {isCached && (
                <span className="px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 text-[10px]">
                  Cached
                </span>
              )}
            </div>
          )}
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-xl border border-[var(--glass-border)] text-foreground/70 hover:text-foreground transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed relative overflow-hidden group"
            style={{
              background: "linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%)",
              backdropFilter: "blur(10px) saturate(180%)",
              WebkitBackdropFilter: "blur(10px) saturate(180%)",
            }}
          >
            <div className="absolute inset-0 bg-gradient-to-br from-white/10 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-xl" />
            <RefreshCw className={cn("w-4 h-4 relative z-10", loading && "animate-spin")} />
            <span className="text-sm relative z-10">Refresh</span>
        </button>
        </div>
      </div>

      {/* Platform Selector & Filters */}
      <div 
        className="backdrop-blur-xl border border-[var(--glass-border)] rounded-2xl p-4 space-y-4 shadow-xl relative transition-all duration-300"
        style={{
          background: "linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%)",
          backdropFilter: "blur(20px) saturate(180%)",
          WebkitBackdropFilter: "blur(20px) saturate(180%)",
        }}
      >
        {/* Simple gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-br from-white/10 via-transparent to-transparent pointer-events-none rounded-2xl" />
        
        <div className="relative z-10 flex items-center gap-4 flex-wrap">
          {/* Platform Dropdown */}
          <DropdownMenuPrimitive.Root>
            <DropdownMenuPrimitive.Trigger asChild>
              <button 
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-[var(--glass-border)] text-foreground text-sm font-medium transition-all duration-300 relative overflow-hidden group"
                style={{
                  background: "linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%)",
                  backdropFilter: "blur(10px) saturate(180%)",
                  WebkitBackdropFilter: "blur(10px) saturate(180%)",
                }}
              >
                <div className="absolute inset-0 bg-gradient-to-br from-white/10 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-xl" />
                <span className="relative z-10">{platforms.find((p) => p.value === selectedPlatform)?.label || "Select Platform"}</span>
                <ChevronDown className="w-4 h-4 text-foreground/50 relative z-10" />
              </button>
            </DropdownMenuPrimitive.Trigger>
            <DropdownMenuPrimitive.Portal>
              <DropdownMenuPrimitive.Content
                align="start"
                className="z-50 min-w-[180px] overflow-hidden rounded-xl border border-[var(--glass-border)] p-1 text-foreground shadow-xl relative"
                style={{
                  background: "linear-gradient(135deg, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0.08) 100%)",
                  backdropFilter: "blur(20px) saturate(180%)",
                  WebkitBackdropFilter: "blur(20px) saturate(180%)",
                }}
              >
                {/* Simple gradient overlay */}
                <div className="absolute inset-0 bg-gradient-to-br from-white/10 via-transparent to-transparent pointer-events-none rounded-xl" />
                {platforms.map((platform) => (
                  <DropdownMenuPrimitive.Item
                    key={platform.value}
                    disabled={platform.disabled}
                    onSelect={() => !platform.disabled && setSelectedPlatform(platform.value)}
                    className={cn(
                      "relative flex select-none items-center gap-3 rounded-lg px-3 py-2.5 text-sm outline-none transition-colors cursor-pointer z-10",
                      platform.disabled
                        ? "opacity-40 cursor-not-allowed"
                        : "hover:bg-foreground/5 focus:bg-foreground/5",
                      selectedPlatform === platform.value && "bg-foreground/10"
                    )}
                  >
                    {selectedPlatform === platform.value && (
                      <Check className="w-4 h-4 text-foreground/70" />
                    )}
                    <span>{platform.label}</span>
                  </DropdownMenuPrimitive.Item>
                ))}
              </DropdownMenuPrimitive.Content>
            </DropdownMenuPrimitive.Portal>
          </DropdownMenuPrimitive.Root>

          {/* Filter Toggle */}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={cn(
              "flex items-center gap-2 px-4 py-2.5 rounded-xl border border-[var(--glass-border)] transition-all duration-300 relative overflow-hidden group",
              showFilters
                ? "text-foreground"
                : "text-foreground/70 hover:text-foreground"
            )}
            style={{
              background: showFilters 
                ? "linear-gradient(135deg, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0.08) 100%)"
                : "linear-gradient(135deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.04) 100%)",
              backdropFilter: "blur(10px) saturate(180%)",
              WebkitBackdropFilter: "blur(10px) saturate(180%)",
            }}
          >
            <div className="absolute inset-0 bg-gradient-to-br from-white/10 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-xl" />
            <Filter className="w-4 h-4 relative z-10" />
            <span className="text-sm font-medium relative z-10">Filters</span>
          </button>

          {/* Sort Dropdown */}
          <div className="flex items-center gap-2 ml-auto">
            <span className="text-xs text-foreground/60">Sort by:</span>
            <DropdownMenuPrimitive.Root>
              <DropdownMenuPrimitive.Trigger asChild>
                <button 
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[var(--glass-border)] text-foreground text-xs font-medium transition-all duration-300 relative overflow-hidden group"
                  style={{
                    background: "linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%)",
                    backdropFilter: "blur(10px) saturate(180%)",
                    WebkitBackdropFilter: "blur(10px) saturate(180%)",
                  }}
                >
                  <div className="absolute inset-0 bg-gradient-to-br from-white/10 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-lg" />
                  <span className="relative z-10">{sortOptions.find((o) => o.value === sortBy)?.label || "Engagement"}</span>
                  <ChevronDown className="w-3 h-3 text-foreground/50 relative z-10" />
                </button>
              </DropdownMenuPrimitive.Trigger>
              <DropdownMenuPrimitive.Portal>
              <DropdownMenuPrimitive.Content
                align="end"
                className="z-50 min-w-[140px] overflow-hidden rounded-xl border border-[var(--glass-border)] p-1 text-foreground shadow-xl relative"
                style={{
                  background: "linear-gradient(135deg, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0.08) 100%)",
                  backdropFilter: "blur(20px) saturate(180%)",
                  WebkitBackdropFilter: "blur(20px) saturate(180%)",
                }}
              >
                  {/* Simple gradient overlay */}
                  <div className="absolute inset-0 bg-gradient-to-br from-white/10 via-transparent to-transparent pointer-events-none rounded-xl" />
                  {sortOptions.map((option) => (
                    <DropdownMenuPrimitive.Item
                      key={option.value}
                      onSelect={() => setSortBy(option.value)}
                      className={cn(
                        "relative flex select-none items-center gap-3 rounded-lg px-3 py-2 text-xs outline-none transition-colors hover:bg-foreground/5 focus:bg-foreground/5 cursor-pointer z-10",
                        sortBy === option.value && "bg-foreground/10"
                      )}
                    >
                      {sortBy === option.value && (
                        <Check className="w-3 h-3 text-foreground/70" />
                      )}
                      <span>{option.label}</span>
                    </DropdownMenuPrimitive.Item>
                  ))}
                </DropdownMenuPrimitive.Content>
              </DropdownMenuPrimitive.Portal>
            </DropdownMenuPrimitive.Root>
            <button
              onClick={() => setSortOrder(sortOrder === "desc" ? "asc" : "desc")}
              className="px-2 py-1.5 rounded-lg border border-[var(--glass-border)] text-foreground/70 hover:text-foreground transition-all duration-300 relative overflow-hidden group"
              style={{
                background: "linear-gradient(135deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.04) 100%)",
                backdropFilter: "blur(10px) saturate(180%)",
                WebkitBackdropFilter: "blur(10px) saturate(180%)",
              }}
              title={sortOrder === "desc" ? "Descending" : "Ascending"}
            >
              <div className="absolute inset-0 bg-gradient-to-br from-white/10 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-lg" />
              <span className="relative z-10">{sortOrder === "desc" ? "↓" : "↑"}</span>
            </button>
                </div>
              </div>

        {/* Expanded Filters */}
        {showFilters && (
          <div className="relative z-10 pt-4 border-t border-[var(--glass-border)]">
            <div className="flex items-center gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-foreground/50" />
                <input
                  type="text"
                  placeholder="Search by keyword..."
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 border border-[var(--glass-border)] rounded-xl text-foreground text-sm placeholder:text-foreground/40 focus:outline-none focus:ring-2 focus:ring-primary/40 transition-all duration-300 relative"
                  style={{
                    background: "linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%)",
                    backdropFilter: "blur(10px) saturate(180%)",
                    WebkitBackdropFilter: "blur(10px) saturate(180%)",
                  }}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/40 text-red-200 px-4 py-3 rounded-xl text-sm">
          {error}
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-foreground/60" />
        </div>
      )}

      {/* Trends List */}
      {!loading && !error && (
        <div className="space-y-3">
          {filteredAndSortedTrends.length === 0 ? (
            <div className="text-center py-12 text-foreground/60">
              <p>No trends found matching your filters.</p>
            </div>
          ) : (
            filteredAndSortedTrends.map((trend, index) => {
              const analyzablePayload: AnalyzableNews = {
                id: trend.url || `${selectedPlatform}-${index}`,
                title: trend.title,
                summary: trend.description,
                content: trend.description,
                sourceName: selectedPlatform === "reddit" ? `r/${trend.source}` : trend.source,
                sourceType: selectedPlatform,
                url: trend.url,
                publishedAt: trend.created_utc,
                metadata: {
                  author: trend.author,
                  score: trend.score,
                  comments: trend.num_comments,
                  platform: selectedPlatform,
                },
              };

              return (
                <div
                  key={`${trend.url}-${index}`}
                  className="bg-[var(--glass-bg)] backdrop-blur-xl border border-[var(--glass-border)] rounded-2xl p-5 hover:border-foreground/30 transition-all duration-300 relative overflow-hidden group shadow-xl"
                  style={{
                    background: "linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%)",
                    backdropFilter: "blur(20px) saturate(180%)",
                    WebkitBackdropFilter: "blur(20px) saturate(180%)",
                  }}
                >
                  {/* Simple gradient overlay on hover */}
                  <div className="absolute inset-0 bg-gradient-to-br from-white/10 via-transparent to-transparent pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-2xl" />

                  <div className="relative z-10">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 mb-2">
                          <span className="text-foreground/40 font-bold text-lg shrink-0">
                            #{index + 1}
                          </span>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs px-2 py-0.5 rounded-full bg-foreground/10 text-foreground/70 font-medium">
                              {selectedPlatform === "reddit" ? `r/${trend.source}` : trend.source}
                            </span>
                            {trend.flair && (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400">
                                {trend.flair}
                              </span>
                            )}
                            {trend.is_nsfw && (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/20 text-red-400">
                                NSFW
                              </span>
                            )}
                          </div>
                        </div>

                        <h3 className="font-bold text-foreground mb-2 transition-all duration-300 line-clamp-2">
                          {trend.title}
                        </h3>

                        {trend.description && (
                          <p className="text-sm text-foreground/70 line-clamp-2 mb-3">
                            {trend.description}
                          </p>
                        )}

                        <div className="flex items-center gap-4 text-xs text-foreground/50">
                          {selectedPlatform === "reddit" && (
                            <>
                              <div className="flex items-center gap-1">
                                <TrendingUp className="w-3.5 h-3.5" />
                                <span>{formatNumber(trend.score)}</span>
                              </div>
                              <div className="flex items-center gap-1">
                                <MessageSquare className="w-3.5 h-3.5" />
                                <span>{formatNumber(trend.num_comments)}</span>
                              </div>
                            </>
                          )}
                          {selectedPlatform === "telegram" && (
                            <>
                              <div className="flex items-center gap-1">
                                <TrendingUp className="w-3.5 h-3.5" />
                                <span>{formatNumber(trend.score)}</span>
                                <span className="text-[10px] uppercase tracking-wide">Views</span>
                              </div>
                              <div className="flex items-center gap-1">
                                <MessageSquare className="w-3.5 h-3.5" />
                                <span>{formatNumber(trend.num_comments)}</span>
                                <span className="text-[10px] uppercase tracking-wide">Forwards</span>
                              </div>
                            </>
                          )}
                          {trend.author && (
                            <div className="flex items-center gap-1">
                              <span>by {trend.author}</span>
                            </div>
                          )}
                          <div className="flex items-center gap-1">
                            <Calendar className="w-3.5 h-3.5" />
                            <span>{formatDate(trend.created_utc)}</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex flex-col items-end gap-2 shrink-0">
                        {(selectedPlatform === "reddit" || selectedPlatform === "telegram") && (
                          <div 
                            className="text-right backdrop-blur-xl border border-[var(--glass-border)] rounded-xl px-4 py-3 shadow-xl relative transition-all duration-300"
                            style={{
                              background: "linear-gradient(135deg, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0.05) 100%)",
                              backdropFilter: "blur(20px) saturate(180%)",
                              WebkitBackdropFilter: "blur(20px) saturate(180%)",
                            }}
                          >
                            {/* Simple gradient overlay */}
                            <div className="absolute inset-0 bg-gradient-to-br from-white/10 via-transparent to-transparent pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-xl" />
                            
                            <div className="relative z-10">
                              <div className="text-xs text-foreground/50 mb-1">Engagement</div>
                              <div className="text-xl font-bold text-green-400">
                                {formatNumber(Math.round(trend.engagement_score))}
                              </div>
                            </div>
                          </div>
                        )}
                        <ArrowUpRight className="w-5 h-5 text-foreground/30 group-hover:text-foreground/60 transition-colors duration-300" />
                      </div>
                    </div>
                    <div className="mt-4 flex flex-wrap items-center gap-3">
                      <AnalyzeNewsButton news={analyzablePayload} size="sm" />
                      {trend.url && (
                        <a
                          href={trend.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-foreground/60 hover:text-foreground inline-flex items-center gap-1"
                        >
                          Open source <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      )}

      {/* Info Footer */}
      {!loading && !error && filteredAndSortedTrends.length > 0 && (
        <div className="text-center text-xs text-foreground/50 pt-4">
          Showing top 10 of {trends.length} trends • Sorted by {sortBy} ({sortOrder})
        </div>
      )}
    </div>
  );
}
