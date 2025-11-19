import type { Metadata } from "next";
import { HomeLanding } from "../components/home/home-landing";

export const metadata: Metadata = {
  title: "TTRPG Center - Home"
};

export const dynamic = "force-dynamic";

export default function Home() {
  return <HomeLanding />;
}
