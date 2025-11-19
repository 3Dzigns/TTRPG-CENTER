import { z } from "zod";
import { zodToJsonSchema } from "zod-to-json-schema";

export const queryScopeSchema = z.literal("game");

export const queryMessageRoleSchema = z.enum(["system", "user", "assistant"]);

export const queryMessageSchema = z.object({
  role: queryMessageRoleSchema,
  content: z
    .string()
    .min(1, "Message content cannot be empty")
    .max(4000, "Message content exceeds 4000 character limit"),
  metadata: z.record(z.unknown()).optional()
});

export const queryRequestSchema = z.object({
  scope: queryScopeSchema,
  gameId: z.string().min(1, "gameId is required"),
  actorId: z.string().min(1, "actorId is required"),
  characterId: z
    .string()
    .min(1)
    .nullable()
    .optional(),
  messages: z.array(queryMessageSchema).min(1, "At least one message is required"),
  sourceIds: z.array(z.string().min(1)).min(1).optional(),
  metadata: z.record(z.unknown()).optional()
});

export const queryRunStatusSchema = z.enum([
  "queued",
  "in_progress",
  "streaming",
  "completed",
  "failed"
]);

export const queryResponseSchema = z.object({
  requestId: z.string().min(1, "requestId is required"),
  status: queryRunStatusSchema,
  issuedAt: z.string().datetime({ offset: true }).optional()
});

export const queryCitationSchema = z.object({
  sourceId: z.string().min(1),
  chunkId: z.string().optional(),
  title: z.string().optional(),
  url: z.string().url().optional()
});

export const queryStatusEventSchema = z.object({
  type: z.literal("query.status"),
  requestId: z.string().min(1),
  status: queryRunStatusSchema,
  answer: z.string().optional(),
  delta: z.string().optional(),
  citations: z.array(queryCitationSchema).optional(),
  error: z.string().optional()
});

export type QueryScope = z.infer<typeof queryScopeSchema>;
export type QueryMessageRole = z.infer<typeof queryMessageRoleSchema>;
export type QueryMessage = z.infer<typeof queryMessageSchema>;
export type QueryRequestInput = z.infer<typeof queryRequestSchema>;
export type QueryRunStatus = z.infer<typeof queryRunStatusSchema>;
export type QueryResponse = z.infer<typeof queryResponseSchema>;
export type QueryCitation = z.infer<typeof queryCitationSchema>;
export type QueryStatusEvent = z.infer<typeof queryStatusEventSchema>;

export const queryRequestJsonSchema = zodToJsonSchema(queryRequestSchema, {
  name: "QueryRequest"
});

export const queryResponseJsonSchema = zodToJsonSchema(queryResponseSchema, {
  name: "QueryResponse"
});

export const queryStatusEventJsonSchema = zodToJsonSchema(queryStatusEventSchema, {
  name: "QueryStatusEvent"
});
