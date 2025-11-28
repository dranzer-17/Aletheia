"use client";
import React, { useState, useEffect } from "react";

export default function DeepfakeDetection() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [result, setResult] = useState<{ 
    deepfakeId: string;
    filename: string; 
    prediction: string; 
    confidence: number; 
    type: string;
    userId: string;
    timestamp: string;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Cleanup preview URL on unmount
  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      setResult(null);
      setError("");
      
      // Revoke old URL if exists
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
      
      // Create preview URL
      const url = URL.createObjectURL(selectedFile);
      setPreviewUrl(url);
    }
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setError("");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const token = localStorage.getItem("token");
      if (!token) {
        setError("Please login to use deepfake detection");
        setLoading(false);
        return;
      }
      
      const res = await fetch("http://localhost:8000/deepfake/predict", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
        },
        body: formData,
      });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Prediction failed");
      }
      const data = await res.json();
      console.log("🔍 Backend response:", data);
      console.log("🔍 Prediction:", data.prediction);
      console.log("🔍 Confidence:", data.confidence);
      setResult(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unknown error occurred");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full">
      {/* Page Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-foreground mb-3 tracking-tight">Deepfake Detection</h1>
        <p className="text-lg text-foreground/60">
          Upload a video or image and let our AI pipeline analyze it for deepfake artifacts.
        </p>
      </div>
      
      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upload & Preview Section */}
        <div className="bg-[var(--glass-bg)] backdrop-blur-xl border border-[var(--glass-border)] rounded-2xl shadow-xl p-6">
          <h2 className="text-xl font-semibold text-foreground mb-4">Select File</h2>
          <form onSubmit={handleSubmit} className="flex flex-col gap-6">
            <div className="relative">
              <input
                id="file-upload"
                type="file"
                accept="video/*,image/*"
                onChange={handleFileChange}
                className="hidden"
              />
              <label
                htmlFor="file-upload"
                className="flex flex-col items-center justify-center w-full h-48 border-2 border-dashed border-[var(--glass-border)] rounded-xl cursor-pointer hover:border-foreground/30 transition-all bg-[var(--glass-bg)] hover:bg-foreground/5"
              >
                {!file ? (
                  <>
                    <svg className="w-12 h-12 text-foreground/40 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                    <p className="text-foreground/70 text-sm">Click to upload video or image</p>
                    <p className="text-foreground/40 text-xs mt-1">MP4, AVI, MOV, JPG, PNG</p>
                  </>
                ) : (
                  <div className="text-center">
                    <p className="text-green-500 font-medium">{file.name}</p>
                    <p className="text-foreground/50 text-sm mt-1">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                  </div>
                )}
              </label>
            </div>

            {previewUrl && file && (
              <div className="rounded-xl overflow-hidden border border-[var(--glass-border)] bg-black">
                {file.type.startsWith('video/') ? (
                  <video
                    src={previewUrl}
                    controls
                    className="w-full max-h-96 object-contain"
                    preload="auto"
                    muted
                    playsInline
                  />
                ) : (
                  <img
                    src={previewUrl}
                    alt="Preview"
                    className="w-full max-h-96 object-contain"
                  />
                )}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !file}
              className="py-3 px-8 rounded-xl bg-foreground text-background font-semibold text-lg shadow-lg hover:bg-foreground/90 hover:scale-105 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Analyzing...
                </span>
              ) : "Detect Deepfake"}
            </button>
          </form>
        </div>

        {/* Results Section */}
        <div className="bg-[var(--glass-bg)] backdrop-blur-xl border border-[var(--glass-border)] rounded-2xl shadow-xl p-6">
          <h2 className="text-xl font-semibold text-foreground mb-4">Analysis Results</h2>
          
          {!result && !error && !loading && (
            <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-center">
              <svg className="w-16 h-16 text-foreground/30 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="text-foreground/50">Upload a file to see analysis results</p>
            </div>
          )}

          {loading && (
            <div className="flex flex-col items-center justify-center h-full min-h-[400px]">
              <div className="relative w-24 h-24 mb-4">
                <div className="absolute inset-0 border-4 border-foreground/20 rounded-full"></div>
                <div className="absolute inset-0 border-4 border-transparent border-t-foreground rounded-full animate-spin"></div>
              </div>
              <p className="text-foreground text-lg">Processing your file...</p>
              <p className="text-foreground/50 text-sm mt-2">This may take a few moments</p>
            </div>
          )}

          {result && (
            <div className="space-y-6">
              {/* Verdict Card */}
              <div className={`backdrop-blur-lg rounded-xl p-6 border-2 ${
                result.prediction === 'REAL' 
                  ? 'bg-green-500/10 border-green-500/50' 
                  : 'bg-red-500/10 border-red-500/50'
              }`}>
                <h3 className="text-sm font-medium text-foreground/60 mb-2">Verdict & Confidence</h3>
                <div className="flex items-center justify-between">
                  <div>
                    <span className={`text-4xl font-bold block ${
                      result.prediction === 'REAL' ? 'text-green-500' : 'text-red-500'
                    }`}>
                      {result.prediction}
                    </span>
                    <div className="mt-2 flex items-baseline gap-2">
                      <p className="text-2xl font-bold text-blue-400">{(result.confidence * 100).toFixed(1)}%</p>
                      <p className="text-xs text-blue-400 font-medium">Confidence Score</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Analysis Summary */}
              <div className="backdrop-blur-lg bg-foreground/5 rounded-xl p-6 border border-[var(--glass-border)]">
                <h3 className="text-sm font-medium text-foreground/60 mb-3">Analysis Summary</h3>
                <p className="text-foreground/70 text-sm leading-relaxed">
                  {result.prediction === 'REAL' 
                    ? `The AI model has analyzed the ${result.type} and determined it to be authentic with ${(result.confidence * 100).toFixed(1)}% confidence. No significant deepfake artifacts were detected.`
                    : `The AI model has detected potential deepfake artifacts in this ${result.type} with ${(result.confidence * 100).toFixed(1)}% confidence. The content may have been synthetically generated or manipulated.`
                  }
                </p>
              </div>

              {/* Confidence Meter */}
              <div className="backdrop-blur-lg bg-foreground/5 rounded-xl p-6 border border-[var(--glass-border)]">
                <h3 className="text-sm font-medium text-foreground/60 mb-3">Confidence Level</h3>
                <div className="w-full bg-foreground/10 rounded-full h-3 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-1000 ${
                      result.prediction === 'REAL' 
                        ? 'bg-gradient-to-r from-green-500 to-green-400' 
                        : 'bg-gradient-to-r from-red-500 to-red-400'
                    }`}
                    style={{ width: `${result.confidence * 100}%` }}
                  />
                </div>
                <div className="flex justify-between mt-2 text-xs text-foreground/40">
                  <span>0%</span>
                  <span>100%</span>
                </div>
              </div>

              {/* File Details */}
              <div className="backdrop-blur-lg bg-foreground/5 rounded-xl p-6 border border-[var(--glass-border)]">
                <h3 className="text-sm font-medium text-foreground/60 mb-4">File Details</h3>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-foreground/70">Detection ID</span>
                    <span className="font-mono text-xs text-foreground bg-foreground/10 px-2 py-1 rounded">#{result.deepfakeId}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-foreground/70">Filename</span>
                    <span className="font-mono text-sm text-foreground truncate max-w-xs">{result.filename}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-foreground/70">Type</span>
                    <span className="px-3 py-1 rounded-full bg-blue-500/20 text-blue-400 text-sm font-medium uppercase">
                      {result.type}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-foreground/70">Size</span>
                    <span className="text-foreground">{file ? (file.size / 1024 / 1024).toFixed(2) : '0'} MB</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-foreground/70">Timestamp</span>
                    <span className="text-foreground text-sm">{new Date(result.timestamp).toLocaleString()}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="flex flex-col items-center justify-center h-full min-h-[400px]">
              <div className="backdrop-blur-lg bg-red-500/10 border border-red-500/50 rounded-xl p-6 text-center">
                <svg className="w-12 h-12 text-red-500 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="text-red-500 font-medium mb-2">Analysis Failed</p>
                <p className="text-foreground/60 text-sm">{error}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
