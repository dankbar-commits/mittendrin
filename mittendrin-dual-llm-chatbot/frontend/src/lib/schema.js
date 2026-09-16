/**
 * Field shapes for the organizer's submission draft.
 *
 * INTERVAL_VALUES, DAY_VALUES, and emptyDraft() mirror backend/app/schemas.py's
 * DraftItem (a Pydantic model) field-for-field — that's the actual source of
 * truth the backend validates against on every /api/extract call. This is a
 * prototype-grade duplication, not a shared package, so keep the two in sync
 * by hand: if you change DraftItem in backend/app/schemas.py, mirror the
 * shape here, and vice versa.
 *
 * ItemSchema and AdapterDataSchema below are different: they're frontend-only,
 * client-side validation run just before the person copies/submits the final
 * result (see ChatContext.jsx). There is currently no backend equivalent —
 * POST /api/submit only sends a confirmation email, it doesn't validate or
 * persist against a matching schema, since there's no database yet (see the
 * "no persistence" notes in backend/app/routes.py and services.py). If a real
 * backend persistence layer is added later, giving it a matching Pydantic
 * schema and validating there too would remove the need to trust
 * client-side validation alone.
 */

import { z } from "zod";

export const INTERVAL_VALUES = [
    "fixed",
    "daily",
    "mon-fri",
    "weekly",
    "bi-weekly",
    "three-weekly",
    "four-weekly",
    "first_of_month",
    "second_of_month",
    "third_of_month",
    "fourth_of_month",
    "last_of_month",
];

export const DAY_VALUES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

/** A fresh, empty draft — mirrors DraftItem's defaults in backend/app/schemas.py. */
export function emptyDraft() {
    return {
        title: null,
        brief: null,
        description: null,
        location: null,
        address: null,
        zip: null,
        city: null,
        website: null,
        onlineOnly: null,
        email: null,
        phone: null,
        mobile: null,
        contact: null,
        responsibleInstitution: null,
        sponsors: null,
        hours: null,
        charge: null,
        accessibility: null,
        directions: null,
        venue: null,
        image: null,
        tags: [],
        recurringEvent: [],
        state: "suggestion",
        latitude: null,
        longitude: null,
        inferredFields: [],
        turnCount: 0,
    };
}

const i18n = z.object({ de: z.string().min(1) });

/** Strict, submit-time shape — only this schema enforces "required".
 * Frontend-only (see the file-level docstring above) — no backend twin. */
export const ItemSchema = z
    .object({
        title: z.string().min(1, "Titel fehlt"),
        state: z.literal("suggestion"),
        brief: i18n,
        description: i18n,

        location: z.string().nullable().optional(),
        address: z.string().nullable().optional(),
        zip: z.string().nullable().optional(),
        city: z.string().nullable().optional(),
        website: z.string().nullable().optional(),
        onlineOnly: z.boolean().nullable().optional(),

        email: z.string().nullable().optional(),
        phone: z.string().nullable().optional(),
        mobile: z.string().nullable().optional(),
        contact: z.string().nullable().optional(),
        responsibleInstitution: z.string().nullable().optional(),
        sponsors: z.string().nullable().optional(),

        hours: z.object({ de: z.string() }).nullable().optional(),
        charge: z.object({ de: z.string() }).nullable().optional(),
        accessibility: z.object({ de: z.string() }).nullable().optional(),
        directions: z.object({ de: z.string() }).nullable().optional(),
        venue: z.object({ de: z.string() }).nullable().optional(),
        image: z.string().nullable().optional(),

        tags: z.array(z.string()).optional(),
        recurring_event: z.string().optional(),

        latitude: z.number().nullable().optional(),
        longitude: z.number().nullable().optional(),
    })
    .refine((item) => Boolean((item.address && item.city) || item.website || item.onlineOnly === true), {
        message:
            "Es fehlt eine Möglichkeit, den Ort zu finden: Adresse + Ort, eine Website, oder ein Hinweis, dass es nur online stattfindet.",
        path: ["location"],
    });

export const AdapterDataSchema = z.object({
    adapter: z.object({
        name: z.literal("web-form"),
        sourceName: z.literal("Nutzereingabe (Prototyp)"),
    }),
    lastUpdate: z.number(),
    itemsRecord: z.record(z.string(), ItemSchema),
});