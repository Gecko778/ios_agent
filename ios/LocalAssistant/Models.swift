import Foundation

struct Coordinates: Codable {
    let longitude: Double
    let latitude: Double
    let accuracy_m: Double?
}

struct TurnRequest: Encodable {
    let text: String
    let location: Coordinates?
    let location_system: String
    let city: String?
    let provider: String?
    let model: String?
}

struct Place: Decodable, Identifiable {
    let id: String
    let name: String
    let address: String
    let distance_m: Int
    let rating: Double?
}

struct Route: Decodable {
    let mode: String
    let distance_m: Int?
    let duration_s: Int?
    let estimated_taxi_yuan: Double?
}

struct HandoffAction: Decodable {
    let id: String
    let kind: String
    let title: String
    let url: String
    let requires_confirmation: Bool
}

struct TurnResponse: Decodable {
    let status: String
    let spoken: String
    let places: [Place]
    let route: Route?
    let action: HandoffAction?
    let detail: String?
}
