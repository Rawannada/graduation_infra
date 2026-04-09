import mongoose from "mongoose";

export enum GenderTypes {
  male = 'male',
  female = 'female'
}

export enum RoleTypes {
  user = 'user',
  admin = 'admin'
}

export interface IUser {
  userName: string,
  email: string,
  password: string,
  role?: RoleTypes,
  createdAt: Date,
  updatedAt: Date,
  OTP?: string,
  confirmed?: boolean,
  changeCredentials?: Date,
  profilePicture?: string
}

const userSchema = new mongoose.Schema<IUser>(
  {
    email: { type: String, required: true, unique: true, trim: true },
    userName: { type: String },
    password: { type: String, required: true },
    role: { type: String, enum: RoleTypes, default: RoleTypes.user },
    OTP: { type: String },
    confirmed: { tyoe: Boolean },
    changeCredentials: { type: Date },
    profilePicture: { type: String }
  },
  {
    timestamps: true,
    toObject: { virtuals: true },
    toJSON: { virtuals: true }
  })

// userSchema.virtual("fullName").set(function(value) {
//   const [fName, lName] = value.split(" ")
//   this.set({fName, lName})
// }).get(function() {
//   return this.fName + " " + this.lName
// })

const userModel = mongoose.models.User || mongoose.model<IUser>('User', userSchema)

export default userModel