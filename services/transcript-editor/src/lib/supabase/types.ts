export interface ParagraphMeta {
  heading: string | null;
  text: string;
}

export interface Database {
  public: {
    Tables: {
      runs: {
        Row: {
          id: string;
          label: string;
          source: string | null;
          type: "extraction" | "reading";
          created_at: string;
        };
        Insert: {
          id?: string;
          label: string;
          source?: string | null;
          type?: "extraction" | "reading";
          created_at?: string;
        };
        Update: {
          id?: string;
          label?: string;
          source?: string | null;
          type?: "extraction" | "reading";
          created_at?: string;
        };
        Relationships: [];
      };
      clips: {
        Row: {
          id: string;
          run_id: string;
          file_name: string;
          source_file: string | null;
          start_sec: number | null;
          end_sec: number | null;
          duration_sec: number | null;
          speech_score: number | null;
          music_score: number | null;
          draft_transcription: string | null;
          corrected_transcription: string | null;
          status: "pending" | "corrected" | "discarded";
          priority: number;
          corrected_at: string | null;
          corrected_by: string | null;
          paragraphs: ParagraphMeta[] | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          run_id: string;
          file_name: string;
          source_file?: string | null;
          start_sec?: number | null;
          end_sec?: number | null;
          duration_sec?: number | null;
          speech_score?: number | null;
          music_score?: number | null;
          draft_transcription?: string | null;
          corrected_transcription?: string | null;
          status?: "pending" | "corrected" | "discarded";
          priority?: number;
          corrected_at?: string | null;
          corrected_by?: string | null;
          paragraphs?: ParagraphMeta[] | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          run_id?: string;
          file_name?: string;
          source_file?: string | null;
          start_sec?: number | null;
          end_sec?: number | null;
          duration_sec?: number | null;
          speech_score?: number | null;
          music_score?: number | null;
          draft_transcription?: string | null;
          corrected_transcription?: string | null;
          status?: "pending" | "corrected" | "discarded";
          priority?: number;
          corrected_at?: string | null;
          corrected_by?: string | null;
          paragraphs?: ParagraphMeta[] | null;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: "clips_run_id_fkey";
            columns: ["run_id"];
            isOneToOne: false;
            referencedRelation: "runs";
            referencedColumns: ["id"];
          },
        ];
      };
      clip_edits: {
        Row: {
          id: string;
          clip_id: string;
          editor_id: string | null;
          field: string;
          old_value: string | null;
          new_value: string | null;
          reason: string | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          clip_id: string;
          editor_id?: string | null;
          field: string;
          old_value?: string | null;
          new_value?: string | null;
          reason?: string | null;
          created_at?: string;
        };
        Update: {
          id?: string;
          clip_id?: string;
          editor_id?: string | null;
          field?: string;
          old_value?: string | null;
          new_value?: string | null;
          reason?: string | null;
          created_at?: string;
        };
        Relationships: [
          {
            foreignKeyName: "clip_edits_clip_id_fkey";
            columns: ["clip_id"];
            isOneToOne: false;
            referencedRelation: "clips";
            referencedColumns: ["id"];
          },
        ];
      };
    };
    Views: {
      [_ in never]: never;
    };
    Functions: {
      [_ in never]: never;
    };
    Enums: {
      [_ in never]: never;
    };
    CompositeTypes: {
      [_ in never]: never;
    };
  };
}

export type Tables<T extends keyof Database["public"]["Tables"]> =
  Database["public"]["Tables"][T]["Row"];
