import { gql } from "@apollo/client";

export const BROWSE_ELEMENTS = gql`
  query BrowseElements(
    $source: String
    $dataType: String
    $first: Int = 20
    $after: String
  ) {
    browseElements(
      source: $source
      dataType: $dataType
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
        hasPreviousPage
        startCursor
        endCursor
      }
      totalCount
    }
  }
`;

export const BROWSE_VALUES = gql`
  query BrowseValues($source: String, $first: Int = 20) {
    browseValues(source: $source, first: $first) {
      sha256
      label
      valueType
      ontologyId
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
      fileName
    }
  }
`;

export const RUN_SUMMARIES = gql`
  query RunSummaries {
    runSummaries {
      runId
      source
      startedAt
      completedAt
      entityCounts
      enrichmentRate
      curationFlags
      timing
    }
  }
`;
