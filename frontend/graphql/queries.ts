import { gql } from "@apollo/client";

export const BROWSE_ELEMENTS = gql`
  query BrowseElements(
    $source: String
    $dataType: DataType
    $hasAnnotations: Boolean
    $searchText: String
    $first: Int = 20
    $after: String
  ) {
    browseElements(
      source: $source
      dataType: $dataType
      hasAnnotations: $hasAnnotations
      searchText: $searchText
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

export const CURATION_QUEUE = gql`
  query CurationQueue($flagType: FlagType, $status: FlagStatus = PENDING, $first: Int = 20, $after: String) {
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

export const GET_ELEMENT = gql`
  query GetElement($sha256: String!) {
    element(sha256: $sha256) {
      sha256
      dataType
      unit
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
