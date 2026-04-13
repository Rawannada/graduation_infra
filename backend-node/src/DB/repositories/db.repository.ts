import {
  HydratedDocument,
  Model,
  ProjectionType,
  QueryFilter,
  QueryOptions,
  UpdateQuery,
  UpdateWriteOpResult,
} from "mongoose";

export abstract class DbRepository<TDocument> {
  constructor(protected readonly model: Model<TDocument>) { }

  async create(data: Partial<TDocument>): Promise<HydratedDocument<TDocument>> {
    return this.model.create(data);
  }
  async findOne(
    filter: QueryFilter<TDocument>,
    select?: ProjectionType<TDocument>,
  ): Promise<HydratedDocument<TDocument> | null> {
    return this.model.findOne(filter);
  }
  async updateOne(
    filter: QueryFilter<TDocument>,
    update: UpdateQuery<TDocument>,
  ): Promise<UpdateWriteOpResult | null> {
    return this.model.updateOne(filter, update);
  }
  async findById(
    id: string,
    options: QueryOptions = {},
  ): Promise<TDocument | null> {
    return this.model.findById(id, null, options);
  }
  async findOneAndUpdate(
    filter: QueryFilter<TDocument>,
    update: UpdateQuery<TDocument>,
    options: QueryOptions = { new: true },
  ): Promise<TDocument | null> {
    return this.model.findOneAndUpdate(filter, update, options);
  }

  async find({
    filter,
    select,
    options,
  }: {
    filter: QueryFilter<TDocument>;
    select?: ProjectionType<TDocument>;
    options?: QueryOptions<TDocument>;
  }): Promise<HydratedDocument<TDocument>[]> {
    return this.model.find(filter, select, options);
  }

  async findOneAndDelete(
    filter: QueryFilter<TDocument>,
    options: QueryOptions = {},
  ): Promise<TDocument | null> {
    return this.model.findOneAndDelete(filter, options);
  }

  async updateMany(
    filter: QueryFilter<TDocument>,
    update: UpdateQuery<TDocument>,
  ): Promise<UpdateWriteOpResult> {
    return this.model.updateMany(filter, update);
  }
}
