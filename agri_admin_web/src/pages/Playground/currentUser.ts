interface UserLike {
  id: string;
}

export function chooseDefaultUserId(currentUser: UserLike | null, users: UserLike[]): string | null {
  if (!currentUser) return null;
  return users.some((user) => user.id === currentUser.id) ? currentUser.id : null;
}
