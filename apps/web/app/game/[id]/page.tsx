import type { Metadata } from "next";
import { GamePageClient } from "./page-client";

export const metadata: Metadata = {
  title: "Game Space — TTRPG Center"
};

interface GamePageProps {
  params: Promise<{
    id: string;
  }>;
}

export default async function GamePage({ params }: GamePageProps) {
  const { id } = await params;
  return <GamePageClient gameId={id} />;
}
