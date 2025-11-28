"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { 
  Activity, 
  ShieldAlert, 
  FileCheck, 
  AlertTriangle, 
  TrendingUp, 
  Clock,
  Loader2,
  LucideIcon 
} from "lucide-react";
import { API_ENDPOINTS } from "@/lib/config";
import { ResponsivePie } from "@nivo/pie";
import { ResponsiveLine } from "@nivo/line";
import { ResponsiveBar } from "@nivo/bar";

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend: string;
  color?: string;
}

interface User {
  full_name?: string | null;
  email: string;
  _id?: string;
}

interface DashboardStats {
  total_claims: number;
  fake_detected: number;
  real_verified: number;
  mixed_unverified: number;
  average_confidence: number;
  average_analysis_time: number;
}

interface MisinformationClaim {
  claimId: string;
  claim_text: string;
  confidence: number;
  created_at: string | null;
  summary: string;
}

interface MisinformationClaim {
  claimId: string;
  claim_text: string;
  confidence: number;
  created_at: string | null;
  summary: string;
}

// Helper for the Card UI
function StatCard({ title, value, icon: Icon, trend, color = "text-foreground" }: StatCardProps) {
  return (
    <div className="bg-[var(--glass-bg)] backdrop-blur-xl border border-[var(--glass-border)] p-6 rounded-xl hover:border-foreground/20 transition-all relative overflow-hidden">
      {/* Gradient overlay for depth */}
      <div className="absolute inset-0 bg-gradient-to-br from-foreground/5 via-transparent to-foreground/10 pointer-events-none" />
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-4">
          <span className="text-xs font-medium text-foreground/50 uppercase tracking-wider">{title}</span>
          <div className="p-2 bg-foreground/10 rounded-lg border border-foreground/10">
            <Icon className={`w-4 h-4 ${color}`} />
          </div>
        </div>
        <div className={`text-3xl font-semibold ${color} mb-1`}>{value}</div>
        <div className="text-xs text-foreground/40 font-medium">{trend}</div>
      </div>
    </div>
  );
}

export default function DashboardHome() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [topMisinformation, setTopMisinformation] = useState<MisinformationClaim[]>([]);
  const [misinformationLoading, setMisinformationLoading] = useState(true);
  const [trendingTopics, setTrendingTopics] = useState<Array<{topic: string; count: number; frequency: number}>>([]);
  const [topicsLoading, setTopicsLoading] = useState(true);
  const router = useRouter();

  // Fetch user
  useEffect(() => {
    const fetchUser = async () => {
      const token = localStorage.getItem("token");
      if (!token) {
        router.push("/auth/login");
        return;
      }

      try {
        const res = await fetch(API_ENDPOINTS.AUTH.ME, {
          headers: { 
            "Authorization": `Bearer ${token}` 
          },
        });
        
        if (res.ok) {
          const userData = await res.json() as User;
          setUser(userData);
        } else {
          localStorage.removeItem("token");
          router.push("/auth/login");
        }
      } catch {
        console.error("Failed to fetch user");
      } finally {
        setLoading(false);
      }
    };

    fetchUser();
  }, [router]);

  // Fetch dashboard stats
  useEffect(() => {
    const fetchStats = async () => {
      const token = localStorage.getItem("token");
      if (!token) return;

      try {
        const res = await fetch(API_ENDPOINTS.CLAIMS.STATS, {
          headers: { 
            "Authorization": `Bearer ${token}` 
          },
        });
        
        if (res.ok) {
          const statsData = await res.json() as DashboardStats;
          console.log("Dashboard stats fetched:", statsData);
          setStats(statsData);
        } else {
          const errorText = await res.text();
          console.error("Failed to fetch stats:", res.status, errorText);
        }
      } catch (error) {
        console.error("Failed to fetch stats:", error);
      } finally {
        setStatsLoading(false);
      }
    };

    const fetchTopMisinformation = async () => {
      const token = localStorage.getItem("token");
      if (!token) return;

      try {
        const res = await fetch(`${API_ENDPOINTS.CLAIMS.TOP_MISINFORMATION}?limit=5`, {
          headers: { 
            "Authorization": `Bearer ${token}` 
          },
        });
        
        if (res.ok) {
          const data = await res.json() as { claims: MisinformationClaim[] };
          console.log("Top misinformation fetched:", data);
          setTopMisinformation(data.claims || []);
        } else {
          const errorText = await res.text();
          console.error("Failed to fetch top misinformation:", res.status, errorText);
        }
      } catch (error) {
        console.error("Failed to fetch top misinformation:", error);
      } finally {
        setMisinformationLoading(false);
      }
    };

    const fetchTrendingTopics = async () => {
      const token = localStorage.getItem("token");
      if (!token) return;

      try {
        const res = await fetch(`${API_ENDPOINTS.CLAIMS.TRENDING_TOPICS}?limit=8`, {
          headers: { 
            "Authorization": `Bearer ${token}` 
          },
        });
        
        if (res.ok) {
          const data = await res.json() as { topics: Array<{topic: string; count: number; frequency: number}> };
          setTrendingTopics(data.topics || []);
        } else {
          console.error("Failed to fetch trending topics:", res.status);
        }
      } catch (error) {
        console.error("Failed to fetch trending topics:", error);
      } finally {
        setTopicsLoading(false);
      }
    };

    if (!loading) {
      fetchStats();
      fetchTopMisinformation();
      fetchTrendingTopics();
    }
  }, [loading]);

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center text-primary">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    );
  }

  // Shiny bright blue color (#0077b6 but brighter and shinier)
  const shinyBlue = "#00a8ff"; // Bright cyan-blue, very shiny and vibrant
  
  // Mock data for charts (static) - using shiny blue for all
  const verdictData = stats ? [
    { id: "Real", label: "Real Verified", value: stats.real_verified, color: shinyBlue },
    { id: "Fake", label: "Fake Detected", value: stats.fake_detected, color: shinyBlue },
    { id: "Mixed", label: "Mixed/Unverified", value: stats.mixed_unverified, color: shinyBlue },
  ].filter(item => item.value > 0) : [
    { id: "Real", label: "Real Verified", value: 45, color: shinyBlue },
    { id: "Fake", label: "Fake Detected", value: 23, color: shinyBlue },
    { id: "Mixed", label: "Mixed/Unverified", value: 12, color: shinyBlue },
  ];

  // Time series data - static upward trend with natural variation
  const timeSeriesData = [
    {
      id: "Claims",
      color: shinyBlue,
      data: [
        { x: "Mon", y: 8 },
        { x: "Tue", y: 12 },
        { x: "Wed", y: 10 },
        { x: "Thu", y: 18 },
        { x: "Fri", y: 22 },
        { x: "Sat", y: 15 },
        { x: "Sun", y: 20 },
      ],
    },
  ];

  // Mock category data - using shiny blue for all
  const categoryData = [
    { category: "Politics", value: 28 },
    { category: "Health", value: 19 },
    { category: "Finance", value: 15 },
    { category: "Technology", value: 12 },
    { category: "Entertainment", value: 8 },
  ];

  return (
    <div className="space-y-8">
      {/* Welcome Section */}
      <div>
        <h1 className="text-2xl font-semibold text-foreground mb-1.5">
          Welcome back, <span className="text-foreground/90 capitalize">{user?.full_name || user?.email}</span>
        </h1>
        <p className="text-sm text-foreground/50">Real-time monitoring active</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatCard 
          title="Total Claims" 
          value={statsLoading ? "..." : (stats?.total_claims || 0)} 
          icon={Activity} 
          trend={statsLoading ? "Loading..." : `${stats?.total_claims || 0} analyzed`}
          color="text-foreground"
        />
        <StatCard 
          title="Fake Detected" 
          value={statsLoading ? "..." : (stats?.fake_detected || 0)} 
          icon={ShieldAlert} 
          trend={statsLoading ? "Loading..." : `${stats?.total_claims ? Math.round((stats.fake_detected / stats.total_claims) * 100) : 0}% of total`}
          color="text-red-400"
        />
        <StatCard 
          title="Real Verified" 
          value={statsLoading ? "..." : (stats?.real_verified || 0)} 
          icon={FileCheck} 
          trend={statsLoading ? "Loading..." : `${stats?.total_claims ? Math.round((stats.real_verified / stats.total_claims) * 100) : 0}% of total`}
          color="text-green-400"
        />
        <StatCard 
          title="Mixed/Unverified" 
          value={statsLoading ? "..." : (stats?.mixed_unverified || 0)} 
          icon={AlertTriangle} 
          trend={statsLoading ? "Loading..." : `${stats?.total_claims ? Math.round((stats.mixed_unverified / stats.total_claims) * 100) : 0}% of total`}
          color="text-yellow-400"
        />
        <StatCard 
          title="Avg Confidence" 
          value={statsLoading ? "..." : `${stats?.average_confidence || 0}%`} 
          icon={TrendingUp} 
          trend={statsLoading ? "Loading..." : "Average score"}
          color="text-blue-400"
        />
        <StatCard 
          title="Avg Time" 
          value={statsLoading ? "..." : `${stats?.average_analysis_time || 0}s`} 
          icon={Clock} 
          trend={statsLoading ? "Loading..." : "Analysis duration"}
          color="text-purple-400"
        />
      </div>

      {/* Bottom Section: Top Misinformation and Charts */}
      <div className="flex gap-6">
        {/* Left Column - 30% width */}
        <div className="w-[30%] flex flex-col gap-4">
        {/* Top Misinformation Claims Card */}
        <div className="bg-[var(--glass-bg)] backdrop-blur-xl border border-[var(--glass-border)] rounded-xl p-3 flex flex-col h-[320px]">
          <div className="mb-2">
            <h3 className="text-base font-semibold text-foreground">Top Misinformation Claims</h3>
            <p className="text-xs text-foreground/50 mt-0.5">Latest fake claims detected</p>
          </div>
          {misinformationLoading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="w-5 h-5 animate-spin text-foreground/50" />
            </div>
          ) : topMisinformation.length > 0 ? (
            <div className="overflow-y-auto flex-1 pr-1.5 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
              <div className="space-y-2">
                {topMisinformation.map((claim, idx) => (
                  <div
                    key={claim.claimId}
                    className="p-3 bg-[var(--glass-bg)] border border-foreground/10 rounded-lg hover:border-foreground/20 hover:shadow-md transition-all cursor-pointer group"
                    onClick={() => router.push(`/dashboard/analyze/${claim.claimId}`)}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 mb-1">
                          <span className="text-xs font-bold text-[#00a8ff] bg-[#00a8ff]/10 px-1.5 py-0.5 rounded border border-[#00a8ff]/20">
                            #{idx + 1}
                          </span>
                          <span className="text-xs text-foreground/50">
                            {claim.created_at ? new Date(claim.created_at).toLocaleDateString('en-US', { 
                              month: 'short', 
                              day: 'numeric' 
                            }) : "Unknown"}
                          </span>
                        </div>
                        <p className="text-xs font-medium text-foreground line-clamp-2 group-hover:text-foreground/80 transition-colors leading-tight">
                          {claim.claim_text}
                        </p>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <div className="text-lg font-bold text-foreground mb-0">
                          {claim.confidence}%
                        </div>
                        <div className="text-xs text-foreground/50">Conf</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-24 text-foreground/40">
              <p className="text-[10px]">No misinformation claims found</p>
            </div>
          )}
        </div>

        {/* Trending Topics Section */}
        <div className="bg-[var(--glass-bg)] backdrop-blur-xl border border-[var(--glass-border)] rounded-xl p-3 flex flex-col h-[320px]">
          <div className="mb-1.5">
            <h3 className="text-base font-semibold text-foreground">Trending Topics</h3>
            <p className="text-xs text-foreground/50 mt-0.5">Most analyzed keywords</p>
          </div>
          {topicsLoading ? (
            <div className="flex items-center justify-center h-20">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-foreground/50" />
            </div>
          ) : trendingTopics.length > 0 ? (
            <div className="overflow-y-auto flex-1 pr-1 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
              <div className="space-y-1.5">
                {trendingTopics.map((topic, idx) => (
                  <div
                    key={topic.topic}
                    className="flex items-center justify-between p-2 bg-[var(--glass-bg)] border border-foreground/10 rounded-lg hover:border-foreground/20 transition-all"
                  >
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <span className="text-xs font-bold text-[#00a8ff] bg-[#00a8ff]/10 px-1.5 py-0.5 rounded border border-[#00a8ff]/20 flex-shrink-0">
                        #{idx + 1}
                      </span>
                      <span className="text-xs font-medium text-foreground truncate">
                        {topic.topic}
                      </span>
                    </div>
                    <div className="text-xs text-foreground/50 flex-shrink-0 ml-2">
                      {topic.count}x
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-20 text-foreground/40">
              <p className="text-[9px]">No topics found</p>
            </div>
          )}
        </div>
        </div>

        {/* Charts Grid - 70% width */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Verdict Distribution Pie Chart */}
        <div className="bg-[var(--glass-bg)] backdrop-blur-xl border border-[var(--glass-border)] rounded-xl p-6">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-foreground">Verdict Distribution</h3>
            <p className="text-xs text-foreground/50 mt-1">Breakdown of claim verdicts</p>
          </div>
          <div className="h-64">
            <ResponsivePie
              data={verdictData}
              margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
              innerRadius={0.5}
              padAngle={2}
              cornerRadius={4}
              activeOuterRadiusOffset={8}
              colors={{ datum: "data.color" }}
              borderWidth={2}
              borderColor={{ from: "color", modifiers: [["darker", 0.2]] }}
              enableArcLinkLabels={true}
              arcLinkLabelsSkipAngle={10}
              arcLinkLabelsTextColor="#999"
              arcLinkLabelsThickness={2}
              arcLinkLabelsColor={{ from: "color" }}
              enableArcLabels={true}
              arcLabelsSkipAngle={10}
              arcLabelsTextColor="#fff"
              theme={{
                tooltip: {
                  container: {
                    background: "rgba(0, 0, 0, 0.9)",
                    color: "#fff",
                    fontSize: "12px",
                    borderRadius: "8px",
                    padding: "8px",
                  },
                },
              }}
              tooltip={({ datum }) => (
                <div className="bg-black/90 text-white px-3 py-2 rounded-lg shadow-lg text-sm">
                  <strong>{datum.label}:</strong> {datum.value} claims
                </div>
              )}
            />
          </div>
        </div>

        {/* Claims Over Time Line Chart */}
        <div className="bg-[var(--glass-bg)] backdrop-blur-xl border border-[var(--glass-border)] rounded-xl p-6">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-foreground">Claims Over Time</h3>
            <p className="text-xs text-foreground/50 mt-1">Weekly analysis activity</p>
          </div>
          <div className="h-64">
            <ResponsiveLine
              data={timeSeriesData}
              margin={{ top: 20, right: 30, bottom: 50, left: 50 }}
              xScale={{ type: "point" }}
              yScale={{
                type: "linear",
                min: "auto",
                max: "auto",
                stacked: false,
                reverse: false,
              }}
              curve="natural"
              axisTop={null}
              axisRight={null}
              axisBottom={{
                tickSize: 5,
                tickPadding: 5,
                tickRotation: 0,
                legend: "Day",
                legendOffset: 40,
                legendPosition: "middle",
              }}
              axisLeft={{
                tickSize: 5,
                tickPadding: 5,
                tickRotation: 0,
                legend: "Claims",
                legendOffset: -40,
                legendPosition: "middle",
              }}
              enableArea={true}
              areaOpacity={0.5}
              useMesh={true}
              colors={[shinyBlue]}
              lineWidth={4}
              pointSize={12}
              pointColor={shinyBlue}
              pointBorderWidth={4}
              pointBorderColor="#ffffff"
              pointLabelYOffset={-12}
              enablePoints={true}
              enablePointLabel={false}
              enableGridX={true}
              enableGridY={true}
              gridXValues={[]}
              gridYValues={[]}
              defs={[
                {
                  id: "gradient",
                  type: "linearGradient",
                  colors: [
                    { offset: 0, color: shinyBlue, opacity: 0.8 },
                    { offset: 100, color: shinyBlue, opacity: 0.1 },
                  ],
                },
              ]}
              fill={[{ match: "*", id: "gradient" }]}
              theme={{
                axis: {
                  ticks: {
                    text: {
                      fill: "rgba(255, 255, 255, 0.6)",
                    },
                  },
                  legend: {
                    text: {
                      fill: "rgba(255, 255, 255, 0.8)",
                    },
                  },
                },
                tooltip: {
                  container: {
                    background: "rgba(0, 0, 0, 0.9)",
                    color: "#fff",
                    fontSize: "12px",
                    borderRadius: "8px",
                    padding: "8px",
                  },
                },
              }}
            />
          </div>
        </div>

        {/* Category Breakdown Bar Chart */}
        <div className="bg-[var(--glass-bg)] backdrop-blur-xl border border-[var(--glass-border)] rounded-xl p-6 lg:col-span-2">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-foreground">Category Breakdown</h3>
            <p className="text-xs text-foreground/50 mt-1">Claims by category</p>
          </div>
          <div className="h-64">
            <ResponsiveBar
              data={categoryData}
              keys={["value"]}
              indexBy="category"
              margin={{ top: 20, right: 30, bottom: 50, left: 60 }}
              padding={0.3}
              valueScale={{ type: "linear" }}
              indexScale={{ type: "band", round: true }}
              colors={[shinyBlue]}
              borderColor={shinyBlue}
              borderWidth={3}
              borderRadius={6}
              axisTop={null}
              axisRight={null}
              axisBottom={{
                tickSize: 5,
                tickPadding: 5,
                tickRotation: 0,
                legend: "Category",
                legendPosition: "middle",
                legendOffset: 40,
              }}
              axisLeft={{
                tickSize: 5,
                tickPadding: 5,
                tickRotation: 0,
                legend: "Claims",
                legendPosition: "middle",
                legendOffset: -50,
              }}
              labelSkipWidth={12}
              labelSkipHeight={12}
              labelTextColor={{ from: "color", modifiers: [["darker", 1.6]] }}
              animate={true}
              motionConfig="gentle"
              theme={{
                axis: {
                  ticks: {
                    text: {
                      fill: "rgba(255, 255, 255, 0.6)",
                    },
                  },
                  legend: {
                    text: {
                      fill: "rgba(255, 255, 255, 0.8)",
                    },
                  },
                },
                tooltip: {
                  container: {
                    background: "rgba(0, 0, 0, 0.9)",
                    color: "#fff",
                    fontSize: "12px",
                    borderRadius: "8px",
                    padding: "8px",
                  },
                },
              }}
            />
          </div>
        </div>
        </div>
      </div>
    </div>
  );
}
