export type Provenance = "SOURCE_SUPPORTED" | "USER_ASSUMED" | "UNKNOWN";
export type EvidenceClass = "DIRECT" | "ANALOGOUS" | "LIMITED" | "UNKNOWN";

export interface Investigation {
  id: number; psi_id: string | null; title: string; description: string | null; source_url: string | null;
  nasa_verified: boolean; is_synthetic: boolean; gravity_context: string | null; gravity_provenance: Provenance;
  n_files: number;
}
export interface Column { index: number; original: string; name: string; unit: string | null; unit_source: string | null; canonical: string | null }
export interface SourceFile {
  id: number; investigation_id: number; filename: string; source_url: string | null; sha256: string; size_bytes: number;
  encoding: string; delimiter: string; imported_at: string; parse_status: string; row_count: number;
  columns: Column[]; column_map: Record<string, number>; warnings: string[]; data_quality: Record<string, number | null>;
  is_synthetic: boolean; pipeline_version: string;
}
export interface InvestigationDetail extends Investigation { files: SourceFile[] }
export interface RecordRow {
  id: number; record_number: number; line_start: number; line_end: number; parse_status: string;
  issues: string[]; raw_values: (string | null)[]; extra_cells: string[]; normalized: Record<string, number | string | null>;
  numeric_status: Record<string, string>;
}
export interface Dashboard {
  investigations: number; source_files: number; records: number; malformed_records: number;
  synthetic_files: number; user_imported_files: number; files_with_warnings: number; recent_files: SourceFile[];
}
export interface TargetCondition { variable: string; value: number; unit: string; tolerance_pct: number }
export interface StructuredQuery {
  text: string; phenomenon: "flame_spread"; material: string | null; required_measurements: string[];
  target_conditions: TargetCondition[]; environment: { name: string | null; provenance: Provenance };
  include_synthetic: boolean;
}
export interface Param {
  variable: string; label: string; role: string; weight: number; column: string | null; unit: string | null;
  available: boolean; match: number | null; status: string; note: string; gap_category: string | null;
  value_summary: { min: number; max: number; n: number } | null; source: string;
}
export interface Gap { parameter: string; required: boolean; status: string; category: string; source: string;
  unit: string | null; value: unknown; detail: string; limitation: string }
export interface EvidenceResult {
  rank: number; investigation_id: number; investigation_title: string; psi_id: string | null; nasa_verified: boolean;
  is_synthetic: boolean; source_file_id: number; source_filename: string; sha256: string; classification: EvidenceClass;
  relevance: number | null; coverage: number; data_quality: Record<string, number | null>; parameters: Param[];
  reasons: string[]; matching: string[]; missing: string[]; mismatches: string[]; explanation: string; gaps: Gap[];
  records_scored: number; records_excluded_malformed: number; gravity_provenance: Provenance;
  gravity_context: string | null; provenance_label: string;
  record_references: { record_id: number; record_number: number; line_start: number; line_end: number; parse_status: string }[];
}
export interface SearchResponse { question_id: number; query: StructuredQuery; results: EvidenceResult[]; note: string | null }
