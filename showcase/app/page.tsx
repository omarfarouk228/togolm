import { HomeContent } from "@/components/home-content";
import { fetchStats } from "@/lib/api";

export const revalidate = 60;

export default async function Home() {
  let stats = null;
  try {
    stats = await fetchStats();
  } catch {
    // API not running — HomeContent handles the offline state
  }

  return <HomeContent stats={stats} />;
}
