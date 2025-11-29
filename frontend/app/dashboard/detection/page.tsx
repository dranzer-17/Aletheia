"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  Activity,
  BookOpen,
  FileText,
  FolderOpen,
  Image as ImageIcon,
  Landmark,
  LineChart,
  Link2,
  Loader2,
  Mic,
  Plus,
  Search,
  Settings2,
  Square,
  Trash2,
  Volume2,
  type LucideIcon,
} from "lucide-react";
import { API_ENDPOINTS } from "@/lib/config";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { createNewsAnalysisSession } from "@/lib/analyzeNews";
import type { AnalyzableNews } from "@/types/news";
import type {
  AgentRecord,
  ClaimVerdict,
} from "@/types/claims";

interface ClaimHistory {
  claimId: string;
  claim_text: string;
  status: string;
  verdict?: string;
  confidence?: number;
  created_at?: string;
  processing_stage?: string;
}

const verdictColors: Record<string, string> = {
  true: "text-green-400",
  false: "text-red-400",
  mixed: "text-yellow-400",
  unknown: "text-foreground/60",
};

interface MediaAttachment {
  id: string;
  type: "image";
  dataUrl: string;
  mimeType: string;
  filename: string;
}

const MAX_MEDIA_ITEMS = 3;

async function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export default function DetectionPage() {
  const router = useRouter();
  const [claimText, setClaimText] = useState("");
  const [claimUrl, setClaimUrl] = useState("");
  const [inputMode, setInputMode] = useState<"text" | "url">("text");
  const [useWebSearch, setUseWebSearch] = useState(false);
  const [forcedAgents, setForcedAgents] = useState<string[]>([]);
  const [showToolsMenu, setShowToolsMenu] = useState(false);
  const [showMediaMenu, setShowMediaMenu] = useState(false);
  const [processingStage, setProcessingStage] = useState<string | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [verdict, setVerdict] = useState<ClaimVerdict | null>(null);
  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [history, setHistory] = useState<ClaimHistory[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [isViewingPastClaim, setIsViewingPastClaim] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [claimPendingDelete, setClaimPendingDelete] = useState<ClaimHistory | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordingStreamRef = useRef<MediaStream | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [mediaAttachments, setMediaAttachments] = useState<MediaAttachment[]>([]);
  const [ttsLoading, setTtsLoading] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const isPlayingRef = useRef<boolean>(false); // Synchronous ref to track playing state
  const audioEventHandlersRef = useRef<{ ended: (() => void) | null; error: ((e: Event) => void) | null }>({ ended: null, error: null });
  const currentAudioIdRef = useRef<string | null>(null); // Track which audio instance is currently playing
  const isUrlMode = inputMode === "url";

  const token = useMemo(() => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("token");
  }, []);

  const fetchWithAuth = useCallback(
    async (url: string, options?: RequestInit) => {
      if (!token) {
        throw new Error("You must be logged in to analyze claims.");
      }
      const isFormData = options?.body instanceof FormData;
      const response = await fetch(url, {
        ...options,
        headers: {
          Authorization: `Bearer ${token}`,
          ...(isFormData ? {} : { "Content-Type": "application/json" }),
          ...(options?.headers || {}),
        },
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Request failed");
      }
      return response.json();
    },
    [token]
  );

  const pollForVerdict = useCallback(
    async (claimId: string): Promise<ClaimVerdict> => {
      const maxAttempts = 75;  // 5 minutes at 4s intervals (75 * 4 = 300 seconds = 5 minutes)
      const interval = 4000;

      for (let attempt = 0; attempt < maxAttempts; attempt++) {
        const data = (await fetchWithAuth(
          API_ENDPOINTS.CLAIMS.VERDICT(claimId)
        )) as ClaimVerdict;

        if (data.status === "processing") {
          setProcessingStage(data.processing_stage ?? "Processing...");
          await sleep(interval);
          continue;
        }

        if (data.status === "completed") {
          setProcessingStage(null);
          return data;
        }

        if (data.status === "failed") {
          setProcessingStage(data.processing_stage ?? "Failed");
          throw new Error(data.error?.message || "Analysis failed. Try again.");
        }

        await sleep(interval);
      }

      throw new Error("Analysis timed out after 5 minutes. Please try again.");
    },
    [fetchWithAuth]
  );

  const fetchAgents = useCallback(
    async (claimId: string) => {
      const data = (await fetchWithAuth(
        API_ENDPOINTS.CLAIMS.AGENTS(claimId)
      )) as { agents: AgentRecord[] };
      return data.agents;
    },
    [fetchWithAuth]
  );

  const fetchClaimAndAgents = useCallback(
    async (claimId: string) => {
      setLoading(true);
      setError(null);
      try {
        const doc = (await fetchWithAuth(
          API_ENDPOINTS.CLAIMS.VERDICT(claimId)
        )) as ClaimVerdict;
        setVerdict(doc);
        setProcessingStage(
          doc.status === "processing" ? doc.processing_stage ?? "Processing..." : null
        );
        const agentOutputs = await fetchAgents(claimId);
        setAgents(agentOutputs);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load claim.");
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [fetchWithAuth, fetchAgents]
  );

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const data = (await fetchWithAuth(API_ENDPOINTS.CLAIMS.LIST)) as {
        claims: ClaimHistory[];
      };
      setHistory(data.claims);
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : "Failed to load claims.");
    } finally {
      setHistoryLoading(false);
    }
  }, [fetchWithAuth]);

  const handleAnalyze = useCallback(async () => {
    const trimmedText = claimText.trim();
    const trimmedUrl = claimUrl.trim();

    if (inputMode === "url") {
      if (!trimmedUrl) {
        setError("Paste a news/article URL to analyze.");
        return;
      }
      if (!/^https?:\/\//i.test(trimmedUrl)) {
        setError("Only valid http(s) URLs are supported.");
        return;
      }
    } else if (!trimmedText && mediaAttachments.length === 0) {
      setError("Provide a claim or attach a photo to analyze.");
      return;
    }

    // Always redirect to dashboard for analysis (supports text, URL, and media)
    // Title should be ONLY the claim text, nothing else
    const cleanTitle = isUrlMode 
      ? (trimmedUrl || "Claim URL")
      : (trimmedText || "Claim");
    
    const analyzable: AnalyzableNews = {
      id: `claim-${Date.now()}`,
      title: cleanTitle,
      summary: undefined,
      content: isUrlMode ? trimmedUrl : trimmedText,
      sourceName: "User claim",
      sourceType: "claim",
      url: isUrlMode ? trimmedUrl : undefined,
      imageUrl: null,
      publishedAt: null,
      sentiment: null,
      mediaAttachments: mediaAttachments.length > 0 ? mediaAttachments : undefined,
      metadata: {
        fromDetectionTab: true,
      },
    };

    try {
      const sessionId = createNewsAnalysisSession(analyzable, {
        useWebSearch,
        forcedAgents,
      });
      router.push(`/dashboard/analyze/${sessionId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start analysis dashboard.");
    }
  }, [
    claimText,
    claimUrl,
    inputMode,
    isUrlMode,
    mediaAttachments,
    useWebSearch,
    forcedAgents,
    router,
  ]);

  const verdictLabel = verdict?.verdict?.toLowerCase() ?? "pending";
  const verdictColor =
    verdictColors[verdictLabel as keyof typeof verdictColors] ??
    "text-foreground";

  const handleStop = () => {
    console.log("🛑 [TTS STOP] handleStop called");
    console.log("🛑 [TTS STOP] audioRef.current:", audioRef.current);
    console.log("🛑 [TTS STOP] isPlayingRef.current:", isPlayingRef.current);
    console.log("🛑 [TTS STOP] isPlaying state:", isPlaying);
    console.log("🛑 [TTS STOP] currentAudioIdRef:", currentAudioIdRef.current);
    
    const currentAudio = audioRef.current;
    
    if (currentAudio) {
      console.log("🛑 [TTS STOP] Audio element found, attempting to stop...");
      console.log("🛑 [TTS STOP] Audio paused state before stop:", currentAudio.paused);
      console.log("🛑 [TTS STOP] Audio currentTime before stop:", currentAudio.currentTime);
      
      try {
        // Remove event listeners FIRST to prevent them from firing
        const handlers = audioEventHandlersRef.current;
        console.log("🛑 [TTS STOP] Removing event listeners:", { 
          hasEnded: !!handlers.ended, 
          hasError: !!handlers.error 
        });
        
        if (handlers.ended) {
          currentAudio.removeEventListener("ended", handlers.ended);
          console.log("🛑 [TTS STOP] Removed 'ended' listener");
        }
        if (handlers.error) {
          currentAudio.removeEventListener("error", handlers.error);
          console.log("🛑 [TTS STOP] Removed 'error' listener");
        }
        
        // Clear handlers immediately
        audioEventHandlersRef.current = { ended: null, error: null };
        console.log("🛑 [TTS STOP] Cleared event handlers ref");
        
        // AGGRESSIVE STOP: Multiple pause attempts
        console.log("🛑 [TTS STOP] Calling pause()...");
        currentAudio.pause();
        currentAudio.pause(); // Call twice
        currentAudio.pause(); // Call three times to be absolutely sure
        
        // Reset position
        console.log("🛑 [TTS STOP] Resetting currentTime to 0...");
        currentAudio.currentTime = 0;
        
        // Stop all tracks if it's a MediaStream (though it shouldn't be)
        if (currentAudio.srcObject) {
          console.log("🛑 [TTS STOP] Found srcObject, stopping tracks...");
          const stream = currentAudio.srcObject as MediaStream;
          stream.getTracks().forEach(track => track.stop());
          currentAudio.srcObject = null;
        }
        
        // Clear source to stop any buffered playback
        console.log("🛑 [TTS STOP] Clearing audio source...");
        currentAudio.src = "";
        currentAudio.removeAttribute("src");
        
        // Force reload to clear any internal state
        console.log("🛑 [TTS STOP] Calling load() to reset audio element...");
        currentAudio.load();
        
        // Verify it's actually paused
        console.log("🛑 [TTS STOP] Verifying paused state after stop...");
        if (!currentAudio.paused) {
          console.warn("🛑 [TTS STOP] Audio still not paused! Forcing pause again...");
          currentAudio.pause();
          currentAudio.currentTime = 0;
        }
        
        console.log("🛑 [TTS STOP] Audio paused state after stop:", currentAudio.paused);
        console.log("🛑 [TTS STOP] Audio currentTime after stop:", currentAudio.currentTime);
        
      } catch (error) {
        console.error("🛑 [TTS STOP] Error stopping audio:", error);
      } finally {
        // Always clean up references, even if errors occurred
        console.log("🛑 [TTS STOP] Cleaning up references...");
        audioRef.current = null;
        isPlayingRef.current = false;
        currentAudioIdRef.current = null;
        console.log("🛑 [TTS STOP] References cleared");
      }
    } else {
      console.log("🛑 [TTS STOP] No audio element found, cleaning up state only");
      // No audio element, but ensure state is clean
      isPlayingRef.current = false;
      currentAudioIdRef.current = null;
    }
    
    // Clean up URL if it exists
    if (audioUrl) {
      console.log("🛑 [TTS STOP] Revoking audio URL...");
      URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
    }
    
    // Update state
    console.log("🛑 [TTS STOP] Updating React state...");
    setIsPlaying(false);
    setTtsLoading(false);
    console.log("🛑 [TTS STOP] Stop complete!");
  };

  const handleSpeak = async (text: string) => {
    console.log("🔊 [TTS SPEAK] handleSpeak called with text length:", text?.length);
    
    if (!text || !text.trim()) {
      console.log("🔊 [TTS SPEAK] No text provided, returning");
      return;
    }

    // If already playing, stop it first
    if (audioRef.current || isPlayingRef.current) {
      console.log("🔊 [TTS SPEAK] Audio already playing, stopping first...");
      handleStop();
      // Wait a bit for stop to complete
      await new Promise(resolve => setTimeout(resolve, 100));
      console.log("🔊 [TTS SPEAK] Stop complete, returning");
      return;
    }

    // Prevent starting if already loading
    if (ttsLoading) {
      console.log("🔊 [TTS SPEAK] Already loading, returning");
      return;
    }

    // Generate unique ID for this audio instance
    const audioId = `audio-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    console.log("🔊 [TTS SPEAK] Generated audio ID:", audioId);
    currentAudioIdRef.current = audioId;

    try {
      console.log("🔊 [TTS SPEAK] Setting loading state...");
      setTtsLoading(true);

      console.log("🔊 [TTS SPEAK] Calling TTS endpoint...");
      // Call TTS endpoint
      const response = await fetch(API_ENDPOINTS.TTS.SPEAK, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text, lang: "en" }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Failed to generate speech" }));
        const errorMessage = errorData.detail || errorData.message || "Failed to generate speech";
        throw new Error(errorMessage);
      }

      console.log("🔊 [TTS SPEAK] TTS response received, creating blob...");
      // Create blob URL from audio response
      const audioBlob = await response.blob();
      const url = URL.createObjectURL(audioBlob);
      console.log("🔊 [TTS SPEAK] Blob URL created:", url.substring(0, 50) + "...");
      setAudioUrl(url);

      // Clean up previous audio if exists (shouldn't happen, but just in case)
      if (audioRef.current) {
        console.warn("🔊 [TTS SPEAK] Previous audio still exists, cleaning up...");
        const previousAudio: HTMLAudioElement = audioRef.current;
        try {
          previousAudio.pause();
          previousAudio.currentTime = 0;
          previousAudio.src = "";
          previousAudio.load();
        } catch (err) {
          console.error("🔊 [TTS SPEAK] Error cleaning up previous audio:", err);
        }
        audioRef.current = null;
      }

      console.log("🔊 [TTS SPEAK] Creating new Audio element...");
      // Play audio
      const audio = new Audio(url);
      audio.volume = 1.0; // Set volume to maximum
      audioRef.current = audio;
      console.log("🔊 [TTS SPEAK] Audio element created and stored in ref");

      // Set up event handlers with audio ID check
      const handleEnded = () => {
        console.log("🔊 [TTS SPEAK] 'ended' event fired for audio ID:", audioId);
        console.log("🔊 [TTS SPEAK] currentAudioIdRef:", currentAudioIdRef.current);
        console.log("🔊 [TTS SPEAK] audioRef.current === audio:", audioRef.current === audio);
        
        // Only process if this is still the current audio
        if (currentAudioIdRef.current === audioId && audioRef.current === audio) {
          console.log("🔊 [TTS SPEAK] Processing 'ended' event...");
          isPlayingRef.current = false;
          setIsPlaying(false);
          URL.revokeObjectURL(url);
          setAudioUrl(null);
          audioRef.current = null;
          currentAudioIdRef.current = null;
          audioEventHandlersRef.current = { ended: null, error: null };
          console.log("🔊 [TTS SPEAK] 'ended' event processed, cleanup complete");
        } else {
          console.log("🔊 [TTS SPEAK] 'ended' event ignored - audio ID mismatch or ref mismatch");
        }
      };

      const handleError = (e: Event) => {
        console.error("🔊 [TTS SPEAK] 'error' event fired:", e);
        console.log("🔊 [TTS SPEAK] currentAudioIdRef:", currentAudioIdRef.current);
        console.log("🔊 [TTS SPEAK] audioRef.current === audio:", audioRef.current === audio);
        
        // Only process if this is still the current audio
        if (currentAudioIdRef.current === audioId && audioRef.current === audio) {
          console.log("🔊 [TTS SPEAK] Processing 'error' event...");
          isPlayingRef.current = false;
          setIsPlaying(false);
          setTtsLoading(false);
          URL.revokeObjectURL(url);
          setAudioUrl(null);
          audioRef.current = null;
          currentAudioIdRef.current = null;
          audioEventHandlersRef.current = { ended: null, error: null };
          setError("Failed to play audio. Please check your browser audio settings.");
          console.log("🔊 [TTS SPEAK] 'error' event processed, cleanup complete");
        } else {
          console.log("🔊 [TTS SPEAK] 'error' event ignored - audio ID mismatch or ref mismatch");
        }
      };

      // Store handlers in ref so they can be removed in handleStop
      audioEventHandlersRef.current = { ended: handleEnded, error: handleError };
      console.log("🔊 [TTS SPEAK] Event handlers created and stored");
      audio.addEventListener("ended", handleEnded);
      audio.addEventListener("error", handleError);
      console.log("🔊 [TTS SPEAK] Event listeners attached");

      // Wait for audio to be ready, then play
      try {
        console.log("🔊 [TTS SPEAK] Setting preload and waiting for audio to be ready...");
        // Preload the audio
        audio.preload = "auto";
        
        // Wait for the audio to be ready
        await new Promise<void>((resolve, reject) => {
          if (audio.readyState >= 2) {
            // Already loaded
            console.log("🔊 [TTS SPEAK] Audio already loaded (readyState >= 2)");
            resolve();
          } else {
            console.log("🔊 [TTS SPEAK] Waiting for 'canplaythrough' event...");
            const onCanPlay = () => {
              console.log("🔊 [TTS SPEAK] 'canplaythrough' event received");
              audio.removeEventListener("canplaythrough", onCanPlay);
              audio.removeEventListener("error", onError);
              resolve();
            };
            const onError = () => {
              console.error("🔊 [TTS SPEAK] Error loading audio");
              audio.removeEventListener("canplaythrough", onCanPlay);
              audio.removeEventListener("error", onError);
              reject(new Error("Audio failed to load"));
            };
            audio.addEventListener("canplaythrough", onCanPlay);
            audio.addEventListener("error", onError);
            audio.load();
          }
        });

        // Check if audio was stopped while loading
        if (currentAudioIdRef.current !== audioId || audioRef.current !== audio) {
          console.log("🔊 [TTS SPEAK] Audio was stopped while loading, aborting play");
          return;
        }

        console.log("🔊 [TTS SPEAK] Audio ready, calling play()...");
        // Now play the audio
        await audio.play();
        
        // Double-check audio ID before updating state
        if (currentAudioIdRef.current === audioId && audioRef.current === audio) {
          console.log("🔊 [TTS SPEAK] Audio playing, updating state...");
          isPlayingRef.current = true;
          setIsPlaying(true);
          setTtsLoading(false);
          console.log("🔊 [TTS SPEAK] State updated, audio should be playing now");
        } else {
          console.log("🔊 [TTS SPEAK] Audio ID mismatch after play, stopping...");
          audio.pause();
          audio.currentTime = 0;
        }
      } catch (playError) {
        console.error("🔊 [TTS SPEAK] Play error:", playError);
        // AbortError is expected if play() is interrupted
        if (playError instanceof Error && playError.name !== "AbortError") {
          console.error("🔊 [TTS SPEAK] Non-abort play error:", playError);
          setError("Failed to play audio. Please check your browser audio settings.");
        } else {
          console.log("🔊 [TTS SPEAK] Play was aborted (expected)");
        }
        isPlayingRef.current = false;
        setIsPlaying(false);
        setTtsLoading(false);
        // Remove event listeners
        const handlers = audioEventHandlersRef.current;
        if (handlers.ended) {
          audio.removeEventListener("ended", handlers.ended);
          console.log("🔊 [TTS SPEAK] Removed 'ended' listener after play error");
        }
        if (handlers.error) {
          audio.removeEventListener("error", handlers.error);
          console.log("🔊 [TTS SPEAK] Removed 'error' listener after play error");
        }
        audioEventHandlersRef.current = { ended: null, error: null };
        // Clean up if audio was created but failed to play
        if (audioRef.current === audio) {
          audioRef.current = null;
          currentAudioIdRef.current = null;
          URL.revokeObjectURL(url);
          setAudioUrl(null);
        }
      }
    } catch (error) {
      console.error("🔊 [TTS SPEAK] TTS error:", error);
      const errorMessage = error instanceof Error ? error.message : "Failed to generate speech";
      setError(`TTS Error: ${errorMessage}`);
      isPlayingRef.current = false;
      setTtsLoading(false);
      setIsPlaying(false);
      currentAudioIdRef.current = null;
    }
  };

  const closeHistoryPanel = () => {
    setShowHistory(false);
  };

  const handleViewHistory = async () => {
    setShowHistory(true);
    await loadHistory();
  };

  const handleViewClaim = async (claim: ClaimHistory) => {
    closeHistoryPanel();
    
    try {
      // Fetch the full claim data to get verdict and summary
      const fullClaim = (await fetchWithAuth(
        API_ENDPOINTS.CLAIMS.VERDICT(claim.claimId)
      )) as ClaimVerdict;

      // Create an AnalyzableNews payload from the claim
      // Title should be ONLY the claim text, nothing else
      const cleanClaimText = claim.claim_text.trim();
      const analyzable: AnalyzableNews = {
        id: claim.claimId,
        title: cleanClaimText.length > 100 
          ? cleanClaimText.substring(0, 100) + "..." 
          : cleanClaimText,
        summary: fullClaim.summary,
        content: cleanClaimText,
        sourceName: "Past claim",
        sourceType: "claim",
        url: undefined,
        imageUrl: null,
        publishedAt: claim.created_at || null,
        sentiment: null,
        metadata: {
          claimId: claim.claimId,
          fromPastClaims: true,
        },
      };

      // Create analysis session and redirect to dashboard
      const sessionId = createNewsAnalysisSession(analyzable, {
        useWebSearch: false, // Past claims don't need web search
        forcedAgents: [],
      });

      router.push(`/dashboard/analyze/${sessionId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open claim dashboard.");
    }
  };

  const handleStartNewClaim = () => {
    setClaimText("");
    setClaimUrl("");
    setInputMode("text");
    setMediaAttachments([]);
    setVerdict(null);
    setAgents([]);
    setProcessingStage(null);
    setIsViewingPastClaim(false);
    closeHistoryPanel();
  };

  const requestDeleteClaim = (claim: ClaimHistory) => {
    setClaimPendingDelete(claim);
    setDeleteDialogOpen(true);
  };

  const confirmDeleteClaim = useCallback(async () => {
    if (!claimPendingDelete) return;
    setDeleteLoading(true);
    try {
      await fetchWithAuth(API_ENDPOINTS.CLAIMS.DELETE(claimPendingDelete.claimId), {
        method: "DELETE",
      });
      await loadHistory();
      if (verdict?.claimId === claimPendingDelete.claimId) {
        setVerdict(null);
        setAgents([]);
        setClaimText("");
        setProcessingStage(null);
        setIsViewingPastClaim(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete claim.");
    } finally {
      setDeleteLoading(false);
      setClaimPendingDelete(null);
    }
  }, [
    claimPendingDelete,
    fetchWithAuth,
    loadHistory,
    verdict,
  ]);

  const formatDate = (date?: string) => {
    if (!date) return "--";
    const d = new Date(date);
    if (Number.isNaN(d.getTime())) return date;
    return d.toLocaleString();
  };

  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 400)}px`;
  }, []);

  const handlePhotoMenuSelect = () => {
    setShowMediaMenu(false);
    fileInputRef.current?.click();
  };

  const fileToBase64 = (file: File) =>
    new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = () => reject(new Error("Failed to read file."));
      reader.readAsDataURL(file);
    });

  const handleMediaSelected = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      event.target.value = "";
      if (!file) return;

      if (!file.type.startsWith("image/")) {
        setError("Only image uploads are supported right now.");
        return;
      }

      if (file.size > 5 * 1024 * 1024) {
        setError("Please upload images smaller than 5 MB.");
        return;
      }

      if (mediaAttachments.length >= MAX_MEDIA_ITEMS) {
        setError(`You can only attach up to ${MAX_MEDIA_ITEMS} images.`);
        return;
      }

      try {
        const dataUrl = await fileToBase64(file);
        setMediaAttachments((prev) => [
          ...prev,
          {
            id:
              typeof crypto !== "undefined" && crypto.randomUUID
                ? crypto.randomUUID()
                : `media-${Date.now()}`,
            type: "image",
            dataUrl,
            mimeType: file.type,
            filename: file.name,
          },
        ]);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to read image.");
      }
    },
    [mediaAttachments.length]
  );

  const removeMediaAttachment = (id: string) => {
    setMediaAttachments((prev) => prev.filter((item) => item.id !== id));
  };

  const handleClaimTextChange = (value: string) => {
    setClaimText(value);
    if (isViewingPastClaim) {
      setIsViewingPastClaim(false);
    }
    adjustTextareaHeight();
  };

  const handleInputModeChange = (mode: "text" | "url") => {
    setInputMode(mode);
    setError(null);
    if (mode === "url") {
      setShowMediaMenu(false);
      setShowToolsMenu(false);
      setMediaAttachments([]);
    }
  };

  const stopRecordingStream = useCallback(() => {
    if (recordingStreamRef.current) {
      recordingStreamRef.current.getTracks().forEach((track) => track.stop());
      recordingStreamRef.current = null;
    }
  }, []);

  const transcribeRecording = useCallback(
    async (audioBlob: Blob) => {
      if (!token) {
        setError("You must be logged in to analyze claims.");
        return;
      }

      setIsTranscribing(true);
      setError(null);
      try {
        const formData = new FormData();
        formData.append("file", audioBlob, "claim-recording.webm");

        const response = await fetch(API_ENDPOINTS.CLAIMS.TRANSCRIBE, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        });

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(payload.detail || "Transcription failed.");
        }
        const text = (payload.text ?? "").trim();
        if (!text) {
          setError("No speech detected in the recording.");
          return;
        }

        setClaimText(text);
        setVerdict(null);
        setAgents([]);
        setProcessingStage(null);
        setIsViewingPastClaim(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to transcribe audio.");
      } finally {
        setIsTranscribing(false);
      }
    },
    [token, setClaimText]
  );

  const handleMicClick = useCallback(async () => {
    if (isTranscribing) return;

    if (typeof window === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setError("Voice capture is not supported in this browser.");
      return;
    }
    if (!("MediaRecorder" in window)) {
      setError("MediaRecorder API is unavailable in this browser.");
      return;
    }

    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      recordingStreamRef.current = stream;
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        stopRecordingStream();
        const blob = new Blob(audioChunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        audioChunksRef.current = [];
        mediaRecorderRef.current = null;
        setIsRecording(false);
        if (blob.size === 0) {
          setError("No audio captured.");
          return;
        }
        await transcribeRecording(blob);
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
    } catch {
      stopRecordingStream();
      mediaRecorderRef.current = null;
      setIsRecording(false);
      setError("Microphone permission denied or unavailable.");
    }
  }, [isRecording, isTranscribing, stopRecordingStream, transcribeRecording]);

  type ForcedAgentOption = {
    key: string;
    label: string;
    icon: LucideIcon;
  };

  const availableForceAgents: ForcedAgentOption[] = [
    { key: "wikipedia", label: "Wikipedia Agent", icon: BookOpen },
    { key: "political", label: "Political Agent", icon: Landmark },
    { key: "health", label: "Health Agent", icon: Activity },
    { key: "finance", label: "Finance Agent", icon: LineChart },
  ];

  const toggleForcedAgent = (key: string) => {
    setForcedAgents((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  };

  useEffect(() => {
    adjustTextareaHeight();
  }, [claimText, adjustTextareaHeight]);

  useEffect(() => {
    return () => {
      console.log("🧹 [CLEANUP] Component unmounting, cleaning up...");
      if (
        mediaRecorderRef.current &&
        mediaRecorderRef.current.state !== "inactive"
      ) {
        mediaRecorderRef.current.stop();
      }
      stopRecordingStream();
      // Cleanup audio with same logic as handleStop
      const currentAudio = audioRef.current;
      if (currentAudio) {
        console.log("🧹 [CLEANUP] Cleaning up audio element...");
        try {
          // Remove event listeners
          const handlers = audioEventHandlersRef.current;
          if (handlers.ended) {
            currentAudio.removeEventListener("ended", handlers.ended);
          }
          if (handlers.error) {
            currentAudio.removeEventListener("error", handlers.error);
          }
          audioEventHandlersRef.current = { ended: null, error: null };
          
          // Stop playback
          currentAudio.pause();
          currentAudio.currentTime = 0;
          currentAudio.src = "";
          currentAudio.load();
        } catch (error) {
          console.error("🧹 [CLEANUP] Error cleaning up audio:", error);
        } finally {
          audioRef.current = null;
          isPlayingRef.current = false;
          currentAudioIdRef.current = null;
        }
      }
      if (audioUrl) {
        console.log("🧹 [CLEANUP] Revoking audio URL...");
        URL.revokeObjectURL(audioUrl);
      }
      console.log("🧹 [CLEANUP] Cleanup complete");
    };
  }, [stopRecordingStream, audioUrl]);

  useEffect(() => {
    let interval: number | undefined;
    if (loading) {
      const start = performance.now();
      setElapsedMs(0);
      interval = window.setInterval(() => {
        setElapsedMs(performance.now() - start);
      }, 100);
    }
    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [loading]);

  useEffect(() => {
    if (!loading) {
      setProcessingStage(null);
    }
  }, [loading]);

  useEffect(() => {
    if (loading) {
      setShowToolsMenu(false);
    }
  }, [loading]);

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold text-foreground">
          Claim & Fake News Detector
        </h1>
        <p className="text-foreground/60">
          Paste a statement and let our agentic pipeline verify it across real
          news, fact-checkers, and specialist agents.
        </p>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/40 text-red-200 px-4 py-3 rounded-xl text-sm">
          {error}
        </div>
      )}

      <div className="bg-card border border-border p-6 rounded-3xl shadow-lg space-y-3">
        {inputMode === "text" ? (
          <div className="relative">
            <textarea
              ref={textareaRef}
              className="w-full min-h-[10rem] max-h-[25rem] bg-card border border-border rounded-2xl p-4 text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 resize-none transition-all overflow-auto"
              placeholder="e.g. The government announced a new policy that ..."
              value={claimText}
              onChange={(e) => handleClaimTextChange(e.target.value)}
            />
          </div>
        ) : (
          <input
            type="url"
            value={claimUrl}
            onChange={(e) => setClaimUrl(e.target.value)}
            className="w-full bg-card border border-border rounded-2xl p-4 text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 transition-all"
            placeholder="https://example.com/news-article"
          />
        )}
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={() => handleInputModeChange(isUrlMode ? "text" : "url")}
            className={`text-xs tracking-wide uppercase rounded-full px-4 py-1.5 transition-all border ${
              isUrlMode
                ? "bg-foreground text-background border-foreground"
                : "bg-card text-foreground/70 border-border hover:text-foreground"
            }`}
          >
            {isUrlMode ? "URL mode active" : "Enable URL mode"}
          </button>
          <div className="flex items-center gap-2">
            <div className="relative">
              <button
                onClick={() => {
                  if (isUrlMode) return;
                  setShowMediaMenu((prev) => !prev);
                }}
                disabled={isUrlMode}
                className={`w-11 h-11 rounded-2xl border border-border flex items-center justify-center transition-all shadow-lg ${
                  isUrlMode
                    ? "bg-card text-foreground/40 cursor-not-allowed opacity-60"
                    : "bg-card text-foreground/70 hover:text-foreground cursor-pointer"
                }`}
                title={isUrlMode ? "URL mode disables attachments" : "Add media"}
                aria-expanded={showMediaMenu}
              >
                <Plus className="w-4 h-4" />
              </button>
              {showMediaMenu && (
                <div className="absolute z-20 top-12 left-0 w-56 rounded-2xl border border-border bg-card shadow-lg p-3 space-y-1">
                  <button
                    onClick={handlePhotoMenuSelect}
                    className="flex items-center gap-2 w-full text-left px-3 py-2 rounded-xl hover:bg-foreground/10 transition-colors text-sm text-foreground cursor-pointer"
                  >
                    <ImageIcon className="w-4 h-4" />
                    Upload photo
                  </button>
                  <button
                    disabled
                    className="flex items-center gap-2 w-full text-left px-3 py-2 rounded-xl text-sm text-foreground/40 cursor-not-allowed"
                  >
                    <FileText className="w-4 h-4" />
                    Document (soon)
                  </button>
                  <button
                    disabled
                    className="flex items-center gap-2 w-full text-left px-3 py-2 rounded-xl text-sm text-foreground/40 cursor-not-allowed"
                  >
                    <Link2 className="w-4 h-4" />
                    URL (soon)
                  </button>
                </div>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleMediaSelected}
              />
            </div>
            <button
              onClick={handleMicClick}
              disabled={isTranscribing || isUrlMode}
              className={`w-11 h-11 rounded-2xl border border-[var(--glass-border)] flex items-center justify-center transition-all shadow-[0_10px_30px_rgba(0,0,0,0.3)] ${
                isRecording
                  ? "bg-red-500/80 text-white hover:bg-red-500"
                  : isUrlMode
                    ? "bg-card text-foreground/40"
                    : "bg-card text-foreground/70 hover:text-foreground"
              } ${
                isTranscribing || isUrlMode ? "cursor-not-allowed opacity-60" : "cursor-pointer"
              }`}
              title={
                isUrlMode
                  ? "Voice input disabled in URL mode"
                  : isTranscribing
                  ? "Transcribing…"
                  : isRecording
                  ? "Stop recording"
                  : "Record a claim"
              }
            >
              {isTranscribing ? (
                <span className="text-[10px] font-semibold tracking-wide">STT</span>
              ) : (
                <Mic className="w-4 h-4" />
              )}
            </button>
            <button
              onClick={() => setUseWebSearch((prev) => !prev)}
              className={`text-xs tracking-wide uppercase rounded-full px-4 py-1.5 transition-all flex items-center gap-2 border border-border cursor-pointer ${
                useWebSearch
                  ? "bg-foreground/20 text-foreground shadow-lg"
                  : "bg-background/40 text-foreground/70"
              }`}
              aria-pressed={useWebSearch}
            >
              <Search className="w-3.5 h-3.5" />
              Web Search
            </button>
            <div className="relative">
              <button
                onClick={() => {
                  if (isUrlMode) return;
                  setShowToolsMenu((prev) => !prev);
                }}
                disabled={isUrlMode}
                className={`text-xs tracking-wide uppercase rounded-full px-4 py-1.5 transition-all flex items-center gap-2 border border-border ${
                  showToolsMenu ? "shadow-[0_10px_30px_rgba(0,0,0,0.35)] bg-foreground/15" : ""
                } ${
                  isUrlMode
                    ? "text-foreground/40 bg-background/30 cursor-not-allowed opacity-60"
                    : "hover:cursor-pointer text-foreground/80 bg-background/40"
                }`}
                aria-expanded={showToolsMenu}
              >
                <Settings2 className="w-3.5 h-3.5" />
                Tools
              </button>
              {showToolsMenu && (
                <div className="absolute top-14 left-0 w-72 rounded-3xl border border-border bg-card p-4 space-y-4 shadow-lg animate-in fade-in slide-in-from-top-2">
                  <div className="flex items-center justify-between text-xs text-foreground/60">
                    <span>Force specific analysts</span>
                    <span className="text-[10px] uppercase tracking-[0.2em] text-foreground/40">
                      Beta
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {availableForceAgents.map((agent) => {
                      const active = forcedAgents.includes(agent.key);
                      const Icon = agent.icon;
                      return (
                        <button
                          key={agent.key}
                          onClick={() => toggleForcedAgent(agent.key)}
                          className={`relative overflow-hidden rounded-full px-4 py-2 flex items-center gap-2 transition-all hover:-translate-y-0.5 hover:shadow-[0_10px_30px_rgba(0,0,0,0.35)] hover:cursor-pointer group ${
                            active
                              ? "bg-foreground/10 text-foreground"
                              : "bg-white/5 text-foreground/80"
                          }`}
                        >
                          <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity bg-white/10" />
                          <div className="relative flex items-center gap-2">
                            <Icon className="w-4 h-4" />
                            <span className="text-[11px] font-semibold uppercase tracking-wide">
                              {agent.label}
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                  <div className="text-[11px] text-foreground/50 border-t border-white/5 pt-2">
                    Forcing agents guarantees their run, but may increase compute time and credits.
                  </div>
                </div>
              )}
            </div>
          </div>
          <button
            onClick={handleAnalyze}
            disabled={loading || isViewingPastClaim || isRecording || isTranscribing}
            className={`relative inline-flex items-center justify-center gap-2 rounded-full px-8 py-3 text-base font-semibold ml-auto transition-all shadow-lg disabled:cursor-not-allowed disabled:opacity-60 ${
              loading || isViewingPastClaim || isRecording || isTranscribing
                ? "border border-border bg-card text-foreground/60"
                : "border border-primary/50 bg-primary/10 text-primary hover:bg-primary/20 hover:border-primary hover:text-primary hover:shadow-[0_0_25px_rgba(10,127,255,0.35)] active:scale-[0.97]"
            }`}
          >
            <Activity className="h-5 w-5" />
            <span>{loading ? "Analyzing…" : "Analyze Claim"}</span>
          </button>
        </div>
        {mediaAttachments.length > 0 && (
          <div className="flex flex-wrap gap-3">
            {mediaAttachments.map((item) => (
              <div
                key={item.id}
                className="relative border border-border rounded-2xl overflow-hidden w-28 h-28 shadow-lg"
              >
                <Image
                  src={item.dataUrl}
                  alt={item.filename}
                  fill
                  sizes="112px"
                  className="object-cover"
                  unoptimized
                />
                <button
                  onClick={() => removeMediaAttachment(item.id)}
                  className="absolute top-2 right-2 bg-black/60 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs hover:bg-black/80"
                  title="Remove image"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}
        {(useWebSearch || processingStage || isRecording || isTranscribing) && (
          <div className="flex flex-col gap-2 text-xs text-foreground/60">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {useWebSearch && (
                  <>
                    <span className="text-base leading-none">⚠️</span>
                    <span>Takes longer and consumes more credits when enabled.</span>
                  </>
                )}
              </div>
              {processingStage && (
                <div className="flex items-center gap-2 font-mono text-foreground">
                  <span className="text-[11px] uppercase tracking-wide">
                    {processingStage}
                  </span>
                  <span>{(elapsedMs / 1000).toFixed(2)}s</span>
                </div>
              )}
            </div>
            {(isRecording || isTranscribing) && (
              <div className="flex items-center gap-4 text-foreground/80">
                {isRecording && (
                  <div className="flex items-center gap-2 text-red-400">
                    <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                    <span>Listening… tap the mic to stop.</span>
                  </div>
                )}
                {isTranscribing && (
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-foreground/60 animate-pulse" />
                    <span>Transcribing audio…</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

      </div>

      {verdict && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-card border border-border rounded-2xl p-5 shadow-lg">
              <div className="text-sm text-foreground/60 mb-2">
                Verdict & Confidence
              </div>
              <div className={`text-4xl font-bold capitalize ${verdictColor}`}>
                {verdict.verdict ?? "Pending"}
              </div>
              <p className="text-foreground/70 mt-1">
                Confidence:{" "}
                <span className="font-semibold">
                  {verdict.confidence !== undefined
                    ? `${(verdict.confidence * 100).toFixed(1)}%`
                    : "—"}
                </span>
              </p>
              {verdict.category && (
                <p className="text-xs text-foreground/50 mt-3">
                  Category: {verdict.category} · {verdict.sub_category}
                </p>
              )}
            </div>

            <div className="bg-card border border-border rounded-2xl p-5 shadow-lg">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm text-foreground/60">Summary</div>
                {verdict.summary && (
                  <button
                    onClick={() => {
                      console.log("🔘 [BUTTON] TTS button clicked");
                      console.log("🔘 [BUTTON] isPlaying state:", isPlaying);
                      console.log("🔘 [BUTTON] isPlayingRef.current:", isPlayingRef.current);
                      console.log("🔘 [BUTTON] audioRef.current:", audioRef.current);
                      console.log("🔘 [BUTTON] ttsLoading:", ttsLoading);
                      
                      if (isPlaying || isPlayingRef.current) {
                        console.log("🔘 [BUTTON] Calling handleStop()...");
                        handleStop();
                      } else {
                        console.log("🔘 [BUTTON] Calling handleSpeak()...");
                        handleSpeak(verdict.summary!);
                      }
                    }}
                    disabled={ttsLoading}
                    className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-foreground/10 hover:bg-foreground/20 border border-foreground/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    title={isPlaying ? "Stop playback" : "Read summary aloud"}
                  >
                    {ttsLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin text-foreground/70" />
                    ) : isPlaying ? (
                      <Square className="h-4 w-4 text-foreground/70" />
                    ) : (
                      <Volume2 className="h-4 w-4 text-foreground/70" />
                    )}
                  </button>
                )}
              </div>
              <p className="text-sm text-foreground/80">
                {verdict.summary ??
                  "We are preparing the summary of this claim. Please check back in a moment."}
              </p>
            </div>
          </div>

          {verdict.true_news && (
            <div className="bg-card border border-border rounded-2xl p-5 shadow-lg">
              <div className="text-sm text-foreground/60 mb-2">
                What the evidence actually shows
              </div>
              <p className="text-sm text-foreground/80">{verdict.true_news}</p>
            </div>
          )}

          {!!verdict.sources_used?.length && (
            <div className="bg-card border border-border rounded-2xl p-5 shadow-lg">
              <div className="text-sm text-foreground/60 mb-4">Sources</div>
              <div className="space-y-3 max-h-72 overflow-auto pr-2">
                {verdict.sources_used.map((source, idx) => (
                  <a
                    key={`${source.url}-${idx}`}
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block border border-border rounded-xl px-4 py-3 hover:bg-foreground/5 transition-colors"
                  >
                    <div className="text-sm font-medium text-foreground">
                      {source.source_name}
                    </div>
                    <div className="text-xs text-foreground/60 truncate">
                      {source.url}
                    </div>
                    <div className="text-[11px] text-foreground/50 mt-1 uppercase tracking-wide">
                      Via {source.agent_name ?? "Unknown Agent"}
                    </div>
                  </a>
                ))}
              </div>
            </div>
          )}

          {!!agents.length && (
            <div className="bg-[var(--glass-bg)] border border-[var(--glass-border)] rounded-2xl p-5 backdrop-blur-xl shadow-[0_0_0_1px_rgba(255,255,255,0.08),0_20px_70px_rgba(0,0,0,0.35)] space-y-4">
              <div className="text-sm text-foreground/60">
                Agent Outputs ({agents.length})
              </div>
              <div className="space-y-3">
                {agents.map((agent) => (
                  <details
                    key={agent._id}
                    className="border border-border rounded-xl p-4 bg-card"
                  >
                    <summary className="cursor-pointer text-sm font-semibold text-foreground flex justify-between gap-2">
                      <span>
                        {agent.agent_name ?? agent.agent_key} ·{" "}
                        <span className="text-foreground/60 text-xs uppercase">
                          {agent.agent_type ?? "agent"}
                        </span>
                      </span>
                    </summary>
                    <pre className="mt-3 text-xs text-foreground/70 whitespace-pre-wrap overflow-auto max-h-72 bg-black/20 px-3 py-2 rounded-lg">
                      {JSON.stringify(agent.output, null, 2)}
                    </pre>
                  </details>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {showHistory && (
        <div className="fixed inset-0 z-50">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={closeHistoryPanel}
          />
          <div className="relative h-full ml-auto max-w-lg w-full bg-card border-l border-border shadow-lg p-6 flex flex-col space-y-4 animate-in slide-in-from-right duration-300">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-foreground">
                  Past Claims
                </h2>
                <p className="text-xs text-foreground/60">
                  Tap a claim to reopen its verdict.
                </p>
              </div>
              <button
                onClick={closeHistoryPanel}
                className="text-sm text-foreground/60 hover:text-foreground transition-colors"
              >
                Close
              </button>
            </div>
            {historyError && (
              <div className="text-red-300 text-sm">{historyError}</div>
            )}
            <div className="space-y-3 overflow-y-auto pr-2 flex-1">
              {historyLoading ? (
                <div className="text-sm text-foreground/70">Loading claims…</div>
              ) : history.length === 0 ? (
                <div className="text-sm text-foreground/70">
                  No claims analyzed yet.
                </div>
              ) : (
                history.map((item) => (
                  <div
                    key={item.claimId}
                    className="relative border border-border rounded-2xl p-4 bg-card hover:border-white/30 transition-all group"
                  >
                    <button
                      onClick={() => handleViewClaim(item)}
                      className="text-left w-full space-y-2 cursor-pointer"
                    >
                      <p className="text-sm font-semibold text-foreground group-hover:text-white line-clamp-2">
                        {item.claim_text}
                      </p>
                      <div className="flex items-center justify-between text-[11px] uppercase tracking-wide text-foreground/50">
                        <span>{formatDate(item.created_at)}</span>
                        <span>{item.status}</span>
                      </div>
                      {item.verdict && (
                        <span className="inline-flex text-xs px-2 py-0.5 rounded-full bg-foreground/10 text-foreground/80">
                          Verdict: {item.verdict}
                        </span>
                      )}
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        requestDeleteClaim(item);
                      }}
                      className="absolute bottom-3 right-3 w-8 h-8 rounded-full bg-red-500/15 text-red-300 flex items-center justify-center hover:bg-red-500/25 transition-colors"
                      aria-label="Delete claim"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))
              )}
              <button
                onClick={handleStartNewClaim}
                className="w-full mt-4 py-3 rounded-2xl border border-border text-sm font-semibold text-foreground/80 hover:bg-foreground/10 transition-all"
              >
                + New Claim
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="fixed bottom-24 right-6 z-40">
        <button
          onClick={handleViewHistory}
          className="text-foreground hover:text-foreground/70 transition-colors p-2"
          aria-label="View past claims"
        >
          <FolderOpen className="w-8 h-8" />
        </button>
      </div>

      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={(open) => {
          setDeleteDialogOpen(open);
          if (!open && !deleteLoading) {
            setClaimPendingDelete(null);
          }
        }}
        onConfirm={confirmDeleteClaim}
        title="Delete claim?"
        description={
          claimPendingDelete
            ? `This will permanently remove “${claimPendingDelete.claim_text.slice(
                0,
                80
              )}${claimPendingDelete.claim_text.length > 80 ? "..." : ""}” from your history.`
            : "This will permanently remove the selected claim from your history."
        }
        confirmText={deleteLoading ? "Deleting..." : "Delete"}
        cancelText="Cancel"
      />
    </div>
  );
}