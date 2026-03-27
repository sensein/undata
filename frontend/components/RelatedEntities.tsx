import { EntityTag } from "./EntityTag";

interface RelatedItem {
  entityType: string;
  sha256: string;
  label: string;
}

interface RelatedEntitiesProps {
  title: string;
  items: RelatedItem[];
}

export function RelatedEntities({ title, items }: RelatedEntitiesProps) {
  if (items.length === 0) return null;

  return (
    <div className="mt-6">
      <h2 className="text-lg font-semibold mb-3">{title} ({items.length})</h2>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <EntityTag
            key={item.sha256}
            entityType={item.entityType}
            sha256={item.sha256}
            label={item.label}
          />
        ))}
      </div>
    </div>
  );
}
