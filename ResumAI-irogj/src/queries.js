import { HttpError } from 'wasp/server'

export const getResumes = async (args, context) => {
  if (!context.user) { throw new HttpError(401) }

  return context.entities.Resume.findMany({
    where: { userId: context.user.id }
  });
}

export const getUserCredits = async (args, context) => {
  if (!context.user) { throw new HttpError(401) }
  const user = await context.entities.User.findUnique({
    where: { id: context.user.id },
    select: { credits: true }
  });
  if (!user) throw new HttpError(404, 'User not found.');
  return user.credits;
}
