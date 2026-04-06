import mongoose from "mongoose";

const connectionDB = async () =>{
  mongoose.connect(process.env.DB_URL as unknown as string).then(() =>{
    console.log(`BD connected successfully ${process.env.DB_URL}`);
  }).catch((error) =>{
    console.log(`Fail connecting to DB`);
  })
}

export default connectionDB