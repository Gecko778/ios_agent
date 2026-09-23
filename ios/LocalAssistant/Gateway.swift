import Foundation
import Security

enum GatewayError: LocalizedError {
    case unconfigured
    case invalidResponse
    case server(Int)

    var errorDescription: String? {
        switch self {
        case .unconfigured: "请先在设置中填写网关地址和设备令牌。"
        case .invalidResponse: "网关返回了无法识别的内容。"
        case .server(let code): "网关请求失败（HTTP \(code)）。"
        }
    }
}

enum DeviceSettings {
    static var gatewayURL: String {
        get { UserDefaults.standard.string(forKey: "gatewayURL") ?? "" }
        set { UserDefaults.standard.set(newValue, forKey: "gatewayURL") }
    }

    static var provider: String {
        get { UserDefaults.standard.string(forKey: "provider") ?? "deepseek" }
        set { UserDefaults.standard.set(newValue, forKey: "provider") }
    }

    static var model: String {
        get { UserDefaults.standard.string(forKey: "model") ?? "" }
        set { UserDefaults.standard.set(newValue, forKey: "model") }
    }

    static func token() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "LocalAssistantGateway",
            kSecAttrAccount as String: "deviceToken",
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func setToken(_ value: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "LocalAssistantGateway",
            kSecAttrAccount as String: "deviceToken"
        ]
        SecItemDelete(query as CFDictionary)
        guard let data = value.data(using: .utf8) else { return }
        var newItem = query
        newItem[kSecValueData as String] = data
        SecItemAdd(newItem as CFDictionary, nil)
    }
}

struct Gateway {
    func send(text: String, location: Coordinates?) async throws -> TurnResponse {
        guard let base = URL(string: DeviceSettings.gatewayURL),
              base.scheme == "https",
              let token = DeviceSettings.token(), !token.isEmpty else {
            throw GatewayError.unconfigured
        }
        var request = URLRequest(url: base.appendingPathComponent("v1/agent/turns"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.timeoutInterval = 30
        request.httpBody = try JSONEncoder().encode(
            TurnRequest(text: text, location: location, location_system: "wgs84", city: nil,
                        provider: DeviceSettings.provider, model: DeviceSettings.model.isEmpty ? nil : DeviceSettings.model)
        )
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw GatewayError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else { throw GatewayError.server(http.statusCode) }
        return try JSONDecoder().decode(TurnResponse.self, from: data)
    }
}
