export class AppError extends Error {
  constructor(public message: any, public statusCode?: number){
    super(message)
  }
}