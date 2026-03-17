import { getAliasGroup } from "@/lib/api/aliases";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import Link from "next/link";
import { notFound } from "next/navigation";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function AliasGroupDetailPage({ params }: Props) {
  const { id } = await params;

  let group;
  try {
    group = await getAliasGroup(id);
  } catch {
    notFound();
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{group.name}</h1>
        <div className="mt-2 flex gap-2">
          <Badge variant="outline">{group.sssom_predicate}</Badge>
          {group.confidence != null && (
            <Badge variant="secondary">
              confidence: {group.confidence.toFixed(2)}
            </Badge>
          )}
          <Badge variant="secondary">{group.detection_method}</Badge>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Members ({group.members.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {group.members.map((member, i) => (
              <li key={member.uri || i} className="flex items-center gap-3">
                <Link
                  href={`/elements/${encodeURIComponent(member.uri)}`}
                  className="font-medium text-blue-600 hover:underline"
                >
                  {member.provenance[0]?.name || "unknown"}
                </Link>
                <Badge variant="outline">{member.semantic.data_type}</Badge>
                <Badge variant="secondary">{member.provenance[0]?.source}</Badge>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
