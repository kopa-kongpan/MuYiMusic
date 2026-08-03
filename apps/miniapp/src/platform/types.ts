export type PlatformName = 'weapp' | 'tt'

export interface LoginResult {
  code: string
}

export interface PlatformAdapter {
  readonly name: PlatformName
  login(): Promise<LoginResult>
  authorizePhone(): Promise<unknown>
  requestPayment(parameters: Readonly<Record<string, unknown>>): Promise<void>
  share(parameters: Readonly<Record<string, unknown>>): Promise<void>
  subscribeMessage(templateIds: readonly string[]): Promise<void>
  openCustomerService(): Promise<void>
  getPlatformInfo(): Readonly<Record<string, unknown>>
}

