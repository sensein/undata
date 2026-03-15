import { getElementById } from "@/lib/api/elements";
import { ElementDetail } from "@/components/ElementDetail";
import { notFound } from "next/navigation";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function ElementDetailPage({ params }: Props) {
  const { id } = await params;

  let element;
  try {
    element = await getElementById(id);
  } catch {
    notFound();
  }

  return <ElementDetail element={element} />;
}
