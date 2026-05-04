import { Schema } from "mongoose";

export const mappingSchema = new Schema(
    {
        column: { type: String },
        type: {
            type: String,
            enum: ["number", "string", "date"],
        },
    },
    { _id: false },
);

export const chartSchema = new Schema(
    {
        id: { type: String, required: true },
        title: { type: String, required: true },
        description: { type: String },
        fig: { type: Schema.Types.Mixed },
        chartType: {
            type: String,
            enum: ["bar", "line", "pie", "scatter", "heatmap", "histogram", "area"],
            required: true,
        },

        mapping: {
            x: mappingSchema,
            y: mappingSchema,
            value: mappingSchema,
            category: mappingSchema,
            color: mappingSchema,
        },

        options: {
            aggregation: { type: String },
        },
    },
    { _id: false },
);
