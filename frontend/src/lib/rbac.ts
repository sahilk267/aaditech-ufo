export function hasPermission(userPermissions: string[] | undefined, permission: string): boolean {
  return Boolean(userPermissions?.includes(permission));
}

export function missingPermissions(
  userPermissions: string[] | undefined,
  requiredPermissions: string[]
): string[] {
  return requiredPermissions.filter((permission) => !hasPermission(userPermissions, permission));
}
