'use client'

import { useState, useCallback, useMemo } from 'react'
import CesiumGlobe from '@/components/CesiumGlobe'
import { AnalyzeNewsButton } from '@/components/AnalyzeNewsButton'
import type { AnalyzableNews, NewsMarker } from '@/types/news'
import { API_ENDPOINTS } from '@/lib/config'

interface LocationNews {
  location: {
    city: string | null
    state: string | null
    country: string | null
    country_code: string | null
  }
  articles: Array<{
    article_id: string | null
    title: string
    description: string
    link: string
    image_url: string | null
    source_name: string
    pub_date: string | null
    category: string[]
    sentiment: string | null
  }>
  total_count: number
  search_priority: string
}

export default function GlobePage() {
  const [markers, setMarkers] = useState<NewsMarker[]>([])
  const [selectedMarker, setSelectedMarker] = useState<NewsMarker | null>(null)
  const [locationNews, setLocationNews] = useState<LocationNews | null>(null)
  const [loadingNews, setLoadingNews] = useState(false)
  const [clickedCoords, setClickedCoords] = useState<{ lat: number; lon: number } | null>(null)

  const token = useMemo(() => {
    if (typeof window === 'undefined') return null
    return localStorage.getItem('token')
  }, [])

  const handleMarkerAdd = (marker: NewsMarker) => {
    setMarkers(prev => [...prev, marker])
    console.log('Marker added:', marker)
  }

  const handleMarkerSelect = (marker: NewsMarker) => {
    setSelectedMarker(marker)
    setLocationNews(null) // Clear news when marker is selected
    console.log('Marker selected:', marker)
  }

  const handleCoordinateClick = useCallback(async (lat: number, lon: number) => {
    setClickedCoords({ lat, lon })
    setSelectedMarker(null) // Clear marker selection
    setLoadingNews(true)
    setLocationNews(null)

    try {
      const response = await fetch(API_ENDPOINTS.GLOBE.NEWS, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          latitude: lat,
          longitude: lon,
          limit: 10,
        }),
      })

      if (!response.ok) {
        throw new Error(`Failed to fetch news: ${response.statusText}`)
      }

      const data: LocationNews = await response.json()
      setLocationNews(data)
    } catch (error) {
      console.error('Error fetching location news:', error)
    } finally {
      setLoadingNews(false)
    }
  }, [token])

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-foreground">Live Misinformation Map</h1>
      </div>

      {/* 3D Globe Component */}
      <div className="flex-1 w-full border border-border rounded-xl overflow-hidden bg-black">
        <CesiumGlobe
          markers={markers}
          onMarkerAdd={handleMarkerAdd}
          onMarkerSelect={handleMarkerSelect}
          heatmapEnabled={false}
          clusteringEnabled={false}
          onCoordinateClick={handleCoordinateClick}
        />
      </div>

      {/* Loading state - Overlay */}
      {loadingNews && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="bg-[var(--glass-bg)] backdrop-blur-xl border border-[var(--glass-border)] rounded-lg p-6 shadow-2xl">
            <p className="text-sm text-foreground/70">Fetching news for location...</p>
          </div>
        </div>
      )}

      {/* Location News Display - Overlay Modal */}
      {locationNews && !loadingNews && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          onClick={(e) => {
            // Close when clicking outside the modal (on backdrop)
            if (e.target === e.currentTarget) {
              setLocationNews(null)
              setClickedCoords(null)
            }
          }}
        >
          {/* Backdrop */}
          <div 
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={(e) => {
              e.stopPropagation()
              setLocationNews(null)
              setClickedCoords(null)
            }}
          />
          
          {/* Modal Content */}
          <div 
            className="relative w-full max-w-4xl max-h-[90vh] bg-[var(--glass-bg)] backdrop-blur-xl border border-[var(--glass-border)] rounded-xl shadow-2xl overflow-hidden flex flex-col z-10"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex justify-between items-start p-6 border-b border-[var(--glass-border)]">
              <div>
                <h3 className="font-semibold text-foreground mb-1 text-lg">
                  📍 News for {[
                    locationNews.location.city,
                    locationNews.location.state,
                    locationNews.location.country
                  ].filter(Boolean).join(', ') || 'Location'}
                </h3>
                {clickedCoords && (
                  <p className="text-xs text-foreground/60">
                    Coordinates: {clickedCoords.lat.toFixed(4)}, {clickedCoords.lon.toFixed(4)}
                  </p>
                )}
                <p className="text-xs text-foreground/60 mt-1">
                  {locationNews.total_count} article{locationNews.total_count !== 1 ? 's' : ''}
                </p>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  setLocationNews(null)
                  setClickedCoords(null)
                }}
                className="text-foreground/50 hover:text-foreground transition-colors text-2xl leading-none p-2 hover:bg-foreground/10 rounded-lg"
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-3">
              {locationNews.articles.map((article) => {
                const analyzablePayload: AnalyzableNews = {
                  id: article.article_id || article.link,
                  title: article.title,
                  summary: article.description,
                  content: article.description,
                  sourceName: article.source_name,
                  sourceType: 'globe',
                  url: article.link,
                  imageUrl: article.image_url,
                  publishedAt: article.pub_date,
                  sentiment: article.sentiment,
                  metadata: {
                    priority: locationNews.search_priority,
                    location: locationNews.location,
                    categories: article.category,
                  },
                }

                return (
                  <div
                    key={article.article_id || article.link}
                    className="p-4 rounded-lg border border-[var(--glass-border)] hover:bg-foreground/5 transition-all group"
                  >
                    <div className="flex gap-3">
                      {article.image_url && (
                        <img
                          src={article.image_url}
                          alt={article.title}
                          className="w-24 h-24 object-cover rounded-lg flex-shrink-0"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = 'none'
                          }}
                        />
                      )}
                      <div className="flex-1 min-w-0">
                        <h4 className="font-medium text-foreground group-hover:text-primary transition-colors line-clamp-2 mb-1">
                          {article.title}
                        </h4>
                        <p className="text-sm text-foreground/70 line-clamp-2 mb-2">
                          {article.description}
                        </p>
                        <div className="flex flex-wrap items-center gap-3 text-xs text-foreground/60">
                          <span className="font-medium">{article.source_name}</span>
                          {article.pub_date && (
                            <span>{new Date(article.pub_date).toLocaleDateString()}</span>
                          )}
                          {article.category.length > 0 && (
                            <span className="px-2 py-0.5 rounded-full bg-primary/20 text-primary text-[10px]">
                              {article.category[0]}
                            </span>
                          )}
                          {article.sentiment && (
                            <span className={`px-2 py-0.5 rounded-full text-[10px] ${
                              article.sentiment === 'positive' ? 'bg-green-500/20 text-green-400' :
                              article.sentiment === 'negative' ? 'bg-red-500/20 text-red-400' :
                              'bg-gray-500/20 text-gray-400'
                            }`}>
                              {article.sentiment}
                            </span>
                          )}
                        </div>
                        <div className="mt-3 flex flex-wrap items-center gap-3">
                          <AnalyzeNewsButton news={analyzablePayload} size="sm" />
                          {article.link && (
                            <a
                              href={article.link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-foreground/60 hover:text-foreground"
                            >
                              Open source →
                            </a>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Selected marker info */}
      {selectedMarker && (
        <div className="bg-[var(--glass-bg)] backdrop-blur-xl border border-[var(--glass-border)] rounded-lg p-4">
          <div className="flex justify-between items-start">
            <div>
              <h3 className="font-semibold text-foreground mb-1">{selectedMarker.title}</h3>
              <p className="text-sm text-foreground/70 mb-2">{selectedMarker.description}</p>
              <div className="flex gap-3 text-xs text-foreground/60">
                <span>Category: {selectedMarker.category}</span>
                <span>Severity: <span className={`font-semibold ${
                  selectedMarker.severity === 'critical' ? 'text-red-500' :
                  selectedMarker.severity === 'high' ? 'text-orange-500' :
                  selectedMarker.severity === 'medium' ? 'text-yellow-500' :
                  'text-green-500'
                }`}>{selectedMarker.severity}</span></span>
                <span>Time: {new Date(selectedMarker.timestamp).toLocaleString()}</span>
              </div>
            </div>
            <button
              onClick={() => setSelectedMarker(null)}
              className="text-foreground/50 hover:text-foreground transition-colors"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Markers count */}
      {markers.length > 0 && (
        <div className="text-xs text-foreground/60">
          {markers.length} marker{markers.length !== 1 ? 's' : ''} on map
        </div>
      )}
    </div>
  )
}