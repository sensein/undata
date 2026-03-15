import { PathwayDetail } from "@/components/PathwayDetail";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function PathwayDetailPage({ params }: Props) {
  const { id } = await params;
  return <PathwayDetail pathwayId={id} />;
}
