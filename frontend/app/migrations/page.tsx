import { PathwayList } from "@/components/PathwayList";
import Link from "next/link";

export default function MigrationsPage() {
  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Migration Pathways</h1>
        <Link
          href="/migrations/diff"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          Schema Diff
        </Link>
      </div>
      <PathwayList />
    </div>
  );
}
