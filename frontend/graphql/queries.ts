import { gql } from "@apollo/client";

export const BROWSE_ELEMENTS = gql`
  query BrowseElements(
    $source: String
    $dataType: DataType
    $hasAnnotations: Boolean
    $searchText: String
    $sortBy: String
    $sortOrder: String
    $first: Int = 20
    $after: String
  ) {
    browseElements(
      source: $source
      dataType: $dataType
      hasAnnotations: $hasAnnotations
      searchText: $searchText
      sortBy: $sortBy
      sortOrder: $sortOrder
      first: $first
      after: $after
    ) {
      edges {
        node {
          sha256
          dataType
          unit
          valueDomain
          description
          ontologyAnnotations {
            termUri
            termLabel
            ontology
            mappingRelation
            score
            primary
          }
          provenance {
            source
            className
            name
            description
          }
          fileName
        }
        cursor
      }
      pageInfo {
        hasNextPage
        endCursor
      }
      totalCount
    }
  }
`;

export const BROWSE_SCHEMAS = gql`
  query BrowseSchemas($source: String, $searchText: String, $first: Int = 20, $after: String) {
    browseSchemas(source: $source, searchText: $searchText, first: $first, after: $after) {
      edges {
        node {
          sha256
          description
          properties
          subclassOf
          isMixin
          provenance {
            source
            name
          }
        }
        cursor
      }
      pageInfo {
        hasNextPage
        endCursor
      }
      totalCount
    }
  }
`;

export const BROWSE_VALUES = gql`
  query BrowseValues($source: String, $searchText: String, $first: Int = 20, $after: String) {
    browseValues(source: $source, searchText: $searchText, first: $first, after: $after) {
      edges {
        node {
          sha256
          label
          valueType
          ontologyId
          description
          ontologyAnnotations {
            termUri
            termLabel
            score
            primary
          }
          provenance {
            source
            name
          }
        }
        cursor
      }
      pageInfo {
        hasNextPage
        endCursor
      }
      totalCount
    }
  }
`;

export const RUN_SUMMARIES = gql`
  query RunSummaries($source: String, $first: Int = 20) {
    runSummaries(source: $source, first: $first) {
      edges {
        node {
          runId
          source
          startedAt
          completedAt
          entityCounts
          enrichmentRate
          curationFlags
          timing
        }
        cursor
      }
      pageInfo {
        hasNextPage
        endCursor
      }
      totalCount
    }
  }
`;

export const BROWSE_VALUESETS = gql`
  query BrowseValueSets($source: String, $searchText: String, $first: Int = 50, $after: String) {
    browseValuesets(source: $source, searchText: $searchText, first: $first, after: $after) {
      edges {
        node {
          sha256
          name
          members
          description
          provenance { source name }
          ontologyAnnotations { termUri termLabel ontology score primary }
        }
        cursor
      }
      pageInfo { hasNextPage endCursor }
      totalCount
    }
  }
`;

export const CURATION_QUEUE = gql`
  query CurationQueue($flagType: FlagType, $status: FlagStatus, $first: Int = 50, $after: String) {
    curationQueue(flagType: $flagType, status: $status, first: $first, after: $after) {
      edges {
        node {
          id
          entityType
          entityRef
          flagType
          context
          status
          createdAt
          resolvedAt
          resolvedBy
          resolutionNote
        }
        cursor
      }
      pageInfo {
        hasNextPage
        endCursor
      }
      totalCount
    }
  }
`;

export const RESOLVE_FLAG = gql`
  mutation ResolveFlag($input: ResolveFlagInput!) {
    resolveFlag(input: $input) {
      id
      status
      resolvedBy
      resolutionNote
    }
  }
`;

export const GET_ELEMENT = gql`
  query GetElement($sha256: String!) {
    element(sha256: $sha256) {
      sha256
      dataType
      unit
      unitUri
      pattern
      valueDomain
      description
      minValue
      maxValue
      typeRef
      semantic
      provenance {
        source
        className
        name
        description
      }
      ontologyAnnotations {
        termUri
        termLabel
        ontology
        mappingRelation
        matchLevel
        score
        model
        primary
      }
    }
  }
`;

export const GET_SCHEMA = gql`
  query GetSchema($sha256: String!) {
    schema_(sha256: $sha256) {
      sha256
      subclassOf
      isMixin
      properties
      description
      semantic
      provenance { source className name description }
      ontologyAnnotations { termUri termLabel ontology mappingRelation matchLevel score model primary }
    }
  }
`;

export const GET_VALUE = gql`
  query GetValue($sha256: String!) {
    value(sha256: $sha256) {
      sha256
      label
      valueType
      ontologyId
      description
      semantic
      provenance { source className name description }
      ontologyAnnotations { termUri termLabel ontology mappingRelation score primary }
    }
  }
`;

export const GET_VALUESET = gql`
  query GetValueSet($sha256: String!) {
    valueset(sha256: $sha256) {
      sha256
      name
      members
      description
      semantic
      provenance { source className name description }
      ontologyAnnotations { termUri termLabel ontology score primary }
    }
  }
`;

export const ELEMENT_POPOVER = gql`
  query ElementPopover($sha256: String!) {
    element(sha256: $sha256) {
      sha256 dataType unit description
      provenance { source name }
      ontologyAnnotations { termUri termLabel ontology mappingRelation score primary }
    }
  }
`;

export const SCHEMA_POPOVER = gql`
  query SchemaPopover($sha256: String!) {
    schema_(sha256: $sha256) {
      sha256 description properties
      provenance { source name }
      ontologyAnnotations { termUri termLabel ontology score primary }
    }
  }
`;

export const VALUE_POPOVER = gql`
  query ValuePopover($sha256: String!) {
    value(sha256: $sha256) {
      sha256 label description
      provenance { source name }
      ontologyAnnotations { termUri termLabel ontology score primary }
    }
  }
`;

export const BROWSE_TRANSFORMS = gql`
  query BrowseTransforms($sourceElement: String, $targetElement: String, $functionType: String, $first: Int = 50, $after: String) {
    browseTransforms(sourceElement: $sourceElement, targetElement: $targetElement, functionType: $functionType, first: $first, after: $after) {
      edges {
        node {
          sha256
          sourceElement
          targetElement
          functionType
          inputType
          outputType
          expression
          confidence
          provenance { source name }
        }
        cursor
      }
      pageInfo { hasNextPage endCursor }
      totalCount
    }
  }
`;

export const GET_TRANSFORM = gql`
  query GetTransform($sha256: String!) {
    transform(sha256: $sha256) {
      sha256
      sourceElement
      targetElement
      functionType
      inputType
      outputType
      expression
      expressionType
      confidence
      description
      provenance { source className name description }
    }
  }
`;

export const SCHEMAS_USING_ELEMENT = gql`
  query SchemasUsingElement($sha256: String!, $first: Int = 50) {
    schemasUsingElement(sha256: $sha256, first: $first) {
      edges { node { sha256 provenance { source name } } }
      totalCount
    }
  }
`;

export const ONTOLOGY_SOURCES = gql`
  query OntologySources($active: Boolean) {
    ontologySources(active: $active) {
      id
      name
      displayName
      url
      format
      termCount
      active
      lastRefreshedAt
      createdAt
    }
  }
`;

export const TRANSFORMS_FOR_ELEMENT = gql`
  query TransformsForElement($sha256: String!, $first: Int = 50) {
    transformsForElement(sha256: $sha256, first: $first) {
      edges { node { sha256 sourceElement targetElement functionType inputType outputType } }
      totalCount
    }
  }
`;

export const INGESTION_QUEUE = gql`
  query IngestionQueue($status: String, $first: Int = 50) {
    ingestionQueue(status: $status, first: $first) {
      id
      repositoryUrl
      adapterType
      status
      autoApproved
      entityCounts
      errorMessage
      approvedBy
      startedAt
      completedAt
      createdAt
    }
  }
`;

export const FLAGS_FOR_ENTITY = gql`
  query FlagsForEntity($entityType: String!, $entityRef: String!, $first: Int = 50) {
    flagsForEntity(entityType: $entityType, entityRef: $entityRef, first: $first) {
      edges { node { id flagType status context createdAt } }
      totalCount
    }
  }
`;

export const ENRICHMENT_PROPOSALS = gql`
  query EnrichmentProposals($entityType: String, $entityRef: String, $status: String, $first: Int = 50) {
    enrichmentProposals(entityType: $entityType, entityRef: $entityRef, status: $status, first: $first) {
      id
      entityType
      entityRef
      proposalType
      proposedValue
      reasoning
      confidence
      status
      reviewedBy
      createdAt
    }
  }
`;
