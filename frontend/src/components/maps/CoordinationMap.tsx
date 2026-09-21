import { useEffect } from 'react';
import { Circle, MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

type MapRequest = {
  latitude?: number | null;
  longitude?: number | null;
  hospital_name: string;
  city: string;
};

type MapDonor = {
  donor_id: number;
  safe_display_name: string;
  blood_group: string;
  area?: string | null;
  distance_km?: number | null;
  match_score?: number;
  response_status: string;
  latitude: number;
  longitude: number;
};

type CoordinationMapProps = {
  request: MapRequest;
  donors?: MapDonor[];
  showDonors?: boolean;
  radiusKm?: number;
};

const markerIcon = (tone: string, label: string) => L.divIcon({
  className: 'coordination-marker',
  html: `<span style="background:${tone}">${label}</span>`,
  iconSize: [34, 34],
  iconAnchor: [17, 17],
});

function FitMap({ points }: { points: Array<[number, number]> }) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 1) map.setView(points[0], 12);
    if (points.length > 1) map.fitBounds(points, { padding: [28, 28] });
  }, [map, points]);
  return null;
}

export default function CoordinationMap({ request, donors = [], showDonors = false, radiusKm = 25 }: CoordinationMapProps) {
  if (request.latitude == null || request.longitude == null) {
    return <div className="map-empty">Map unavailable because the request location could not be resolved.</div>;
  }

  const requestPoint: [number, number] = [request.latitude, request.longitude];
  const donorPoints = showDonors ? donors.map((donor) => [donor.latitude, donor.longitude] as [number, number]) : [];
  const points = [requestPoint, ...donorPoints];

  return (
    <div className="coordination-map" aria-label="BloodConnect coordination map">
      <MapContainer center={requestPoint} zoom={12} scrollWheelZoom className="map-canvas">
        <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <FitMap points={points} />
        <Marker position={requestPoint} icon={markerIcon('#b91c1c', 'H')}>
          <Popup><strong>{request.hospital_name}</strong><br />{request.city}</Popup>
        </Marker>
        <Circle center={requestPoint} radius={radiusKm * 1000} pathOptions={{ color: '#b91c1c', fillColor: '#fecaca', fillOpacity: 0.12 }} />
        {showDonors ? donors.map((donor) => {
          const tone = donor.response_status === 'accepted' ? '#166534' : donor.response_status === 'declined' ? '#6b7280' : '#b45309';
          return <Marker key={donor.donor_id} position={[donor.latitude, donor.longitude]} icon={markerIcon(tone, donor.response_status === 'accepted' ? 'A' : donor.response_status === 'declined' ? 'D' : 'P')}>
            <Popup>
              <strong>{donor.safe_display_name}</strong><br />
              {donor.blood_group} • {donor.area || 'Area unavailable'}<br />
              {donor.distance_km == null ? 'Distance unavailable' : `${donor.distance_km} km`} • {donor.response_status}
            </Popup>
          </Marker>;
        }) : null}
      </MapContainer>
      <div className="map-text-summary"><strong>{request.hospital_name}</strong><span>{request.city} • {radiusKm} km coordination radius</span></div>
    </div>
  );
}
