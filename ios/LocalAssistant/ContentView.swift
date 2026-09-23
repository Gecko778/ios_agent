import SwiftUI
import UIKit

struct ContentView: View {
    @State private var input = ""
    @State private var response: TurnResponse?
    @State private var error: String?
    @State private var working = false
    @State private var showSettings = false
    @State private var showInstallAlert = false

    var body: some View {
        NavigationStack {
            Form {
                Section("提问") {
                    TextField("例如：步行到最近的星巴克要多久", text: $input, axis: .vertical)
                    Button(working ? "查询中…" : "发送") {
                        Task { await send() }
                    }
                    .disabled(input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || working)
                }
                if let error { Section { Text(error).foregroundStyle(.red) } }
                if let response {
                    Section("结果") {
                        Text(response.spoken)
                        if let detail = response.detail { Text(detail).font(.caption) }
                        ForEach(response.places) { place in
                            VStack(alignment: .leading) {
                                Text(place.name)
                                Text("\(place.distance_m) 米 · \(place.address)").font(.caption)
                                if let rating = place.rating { Text("高德评分 \(rating.formatted())").font(.caption) }
                            }
                        }
                        if let route = response.route {
                            Text(route.duration_s.map { "预计 \(Int(round(Double($0) / 60))) 分钟" } ?? "路线已找到")
                        }
                        if let action = response.action {
                            Button(action.title) { openAmap(action) }
                        }
                    }
                }
            }
            .navigationTitle("本地助手")
            .toolbar { Button("设置") { showSettings = true } }
            .sheet(isPresented: $showSettings) { SettingsView() }
            .alert("未安装高德地图", isPresented: $showInstallAlert) {
                Button("好", role: .cancel) { }
            } message: { Text("请先安装高德地图，再重新发起导航。") }
        }
    }

    @MainActor
    private func send() async {
        working = true
        error = nil
        defer { working = false }
        do {
            let location = await LocationService().current()
            response = try await Gateway().send(text: input, location: location)
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func openAmap(_ action: HandoffAction) {
        guard action.requires_confirmation,
              let url = URL(string: action.url), url.scheme == "iosamap" else { return }
        guard UIApplication.shared.canOpenURL(url) else { showInstallAlert = true; return }
        UIApplication.shared.open(url)
    }
}

struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var gatewayURL = DeviceSettings.gatewayURL
    @State private var provider = DeviceSettings.provider
    @State private var model = DeviceSettings.model
    @State private var token = ""

    var body: some View {
        NavigationStack {
            Form {
                TextField("https://你的网关域名", text: $gatewayURL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                SecureField("设备令牌（留空则不修改）", text: $token)
                Picker("模型供应商", selection: $provider) {
                    ForEach(["openai", "deepseek", "anthropic", "glm", "kimi"], id: \.self) { Text($0) }
                }
                TextField("模型 ID（留空使用网关默认）", text: $model)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
            }
            .navigationTitle("连接设置")
            .toolbar {
                Button("保存") {
                    DeviceSettings.gatewayURL = gatewayURL.trimmingCharacters(in: .whitespacesAndNewlines)
                    DeviceSettings.provider = provider
                    DeviceSettings.model = model.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !token.isEmpty { DeviceSettings.setToken(token) }
                    dismiss()
                }
            }
        }
    }
}
