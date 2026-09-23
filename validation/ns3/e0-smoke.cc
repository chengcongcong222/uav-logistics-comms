/* E0 smoke: Mobility + Wi-Fi + UDP + FlowMonitor (+ optional CSV waypoint import).
 * Not a scientific model. DEM is intentionally NOT included.
 */
#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/wifi-module.h"

#include <cmath>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("E0Smoke");

struct CsvWaypoint
{
  double t;
  Vector pos;
};

static std::map<std::string, std::vector<CsvWaypoint>>
ReadTraceCsv(const std::string& path)
{
  std::map<std::string, std::vector<CsvWaypoint>> out;
  std::ifstream in(path);
  if (!in)
  {
    NS_ABORT_MSG("Cannot open trace CSV: " << path);
  }
  std::string line;
  bool first = true;
  while (std::getline(in, line))
  {
    if (line.empty())
    {
      continue;
    }
    if (first)
    {
      first = false;
      // header: node_id,time,x,y,z
      continue;
    }
    std::stringstream ss(line);
    std::string node, tStr, xStr, yStr, zStr;
    if (!std::getline(ss, node, ','))
    {
      continue;
    }
    std::getline(ss, tStr, ',');
    std::getline(ss, xStr, ',');
    std::getline(ss, yStr, ',');
    std::getline(ss, zStr, ',');
    if (node.empty() || tStr.empty())
    {
      continue;
    }
    CsvWaypoint wp;
    wp.t = std::stod(tStr);
    wp.pos = Vector(std::stod(xStr), std::stod(yStr), std::stod(zStr));
    out[node].push_back(wp);
  }
  return out;
}

int
main(int argc, char* argv[])
{
  std::string tracePath =
      "/home/ccc/projects/uav-logistics-comms/export/e0_test_trace.csv";
  std::string summaryPath =
      "/home/ccc/projects/uav-logistics-comms/results/ns3/e0_smoke_summary.csv";
  double simTime = 25.0;
  uint32_t packetSize = 200;
  double interval = 1.0;

  CommandLine cmd(__FILE__);
  cmd.AddValue("trace", "CSV path (node_id,time,x,y,z)", tracePath);
  cmd.AddValue("summary", "CSV summary output path", summaryPath);
  cmd.AddValue("simTime", "Simulation time seconds", simTime);
  cmd.AddValue("packetSize", "UDP payload bytes", packetSize);
  cmd.AddValue("interval", "UDP send interval seconds", interval);
  cmd.Parse(argc, argv);

  // Two nodes: fixed G01, mobile U01
  NodeContainer nodes;
  nodes.Create(2);
  Ptr<Node> g01 = nodes.Get(0);
  Ptr<Node> u01 = nodes.Get(1);

  // Mobility: G01 fixed; U01 WaypointMobilityModel
  MobilityHelper mobility;
  Ptr<ListPositionAllocator> fixedAlloc = CreateObject<ListPositionAllocator>();
  fixedAlloc->Add(Vector(0.0, 0.0, 0.0));
  mobility.SetPositionAllocator(fixedAlloc);
  mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
  mobility.Install(g01);

  Ptr<WaypointMobilityModel> uMob = CreateObject<WaypointMobilityModel>();
  u01->AggregateObject(uMob);

  auto traces = ReadTraceCsv(tracePath);
  if (traces.count("U01") == 0)
  {
    NS_ABORT_MSG("Trace missing U01");
  }
  if (traces.count("G01"))
  {
    const auto& gwp = traces["G01"].front();
    Ptr<ConstantPositionMobilityModel> gm =
        g01->GetObject<ConstantPositionMobilityModel>();
    gm->SetPosition(gwp.pos);
  }
  for (const auto& wp : traces["U01"])
  {
    uMob->AddWaypoint(ns3::Waypoint(Seconds(wp.t), wp.pos));
  }
  NS_LOG_UNCOND("U01 waypoints loaded: " << traces["U01"].size());

  // Wi-Fi 2.4 GHz
  YansWifiChannelHelper channel = YansWifiChannelHelper::Default();
  YansWifiPhyHelper phy;
  phy.SetChannel(channel.Create());

  WifiMacHelper mac;
  WifiHelper wifi;
  wifi.SetStandard(WIFI_STANDARD_80211b);
  wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                               "DataMode",
                               StringValue("DsssRate1Mbps"),
                               "ControlMode",
                               StringValue("DsssRate1Mbps"));

  Ssid ssid = Ssid("e0-smoke");
  mac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(ssid));
  NetDeviceContainer staDev = wifi.Install(phy, mac, u01);
  mac.SetType("ns3::ApWifiMac", "Ssid", SsidValue(ssid));
  NetDeviceContainer apDev = wifi.Install(phy, mac, g01);

  // IPv4
  InternetStackHelper internet;
  internet.Install(nodes);
  Ipv4AddressHelper ipv4;
  ipv4.SetBase("10.1.1.0", "255.255.255.0");
  Ipv4InterfaceContainer ifaces = ipv4.Assign(staDev);
  ipv4.Assign(apDev);
  Ipv4Address uAddr = ifaces.GetAddress(0); // U01
  Ipv4Address gAddr = Ipv4Address("10.1.1.2"); // G01 (AP)

  // UDP U01 -> G01
  uint16_t port = 9000;
  UdpServerHelper server(port);
  ApplicationContainer serverApps = server.Install(g01);
  serverApps.Start(Seconds(0.0));
  serverApps.Stop(Seconds(simTime));

  UdpClientHelper client(gAddr, port);
  client.SetAttribute("MaxPackets", UintegerValue(10000));
  client.SetAttribute("Interval", TimeValue(Seconds(interval)));
  client.SetAttribute("PacketSize", UintegerValue(packetSize));
  ApplicationContainer clientApps = client.Install(u01);
  clientApps.Start(Seconds(1.0));
  clientApps.Stop(Seconds(simTime - 1.0));

  FlowMonitorHelper flowmon;
  Ptr<FlowMonitor> monitor = flowmon.InstallAll();

  Simulator::Stop(Seconds(simTime));
  Simulator::Run();

  monitor->CheckForLostPackets();
  Ptr<Ipv4FlowClassifier> classifier =
      DynamicCast<Ipv4FlowClassifier>(flowmon.GetClassifier());
  uint64_t txPackets = 0;
  uint64_t rxPackets = 0;
  uint64_t lostPackets = 0;
  double meanDelayMs = 0.0;
  for (const auto& stat : monitor->GetFlowStats())
  {
    const FlowMonitor::FlowStats& fs = stat.second;
    Ipv4FlowClassifier::FiveTuple t = classifier->FindFlow(stat.first);
    if (t.destinationPort == port)
    {
      txPackets += fs.txPackets;
      rxPackets += fs.rxPackets;
      lostPackets += fs.lostPackets;
      if (rxPackets > 0 && fs.rxPackets > 0)
      {
        meanDelayMs = fs.delaySum.GetMilliSeconds() / static_cast<double>(fs.rxPackets);
      }
      std::cout << "flow " << t.sourceAddress << " -> " << t.destinationAddress
                << " tx=" << fs.txPackets << " rx=" << fs.rxPackets
                << " lost=" << fs.lostPackets << std::endl;
    }
  }

  double pdr = (txPackets > 0) ? static_cast<double>(rxPackets) / static_cast<double>(txPackets)
                               : 0.0;

  std::cout << "tx_packets=" << txPackets << std::endl;
  std::cout << "rx_packets=" << rxPackets << std::endl;
  std::cout << "lost_packets=" << lostPackets << std::endl;
  std::cout << "pdr=" << pdr << std::endl;
  std::cout << "mean_delay_ms=" << meanDelayMs << std::endl;

  // report final U01 position for waypoint sanity
  Vector endPos = uMob->GetPosition();
  std::cout << "U01_end_position=" << endPos.x << "," << endPos.y << "," << endPos.z
            << std::endl;

  {
    std::ofstream out(summaryPath);
    out << "tx_packets,rx_packets,lost_packets,pdr,mean_delay_ms,u01_end_x,u01_end_y,u01_end_z\n";
    out << txPackets << "," << rxPackets << "," << lostPackets << "," << pdr << ","
        << meanDelayMs << "," << endPos.x << "," << endPos.y << "," << endPos.z << "\n";
  }
  std::cout << "summary_written=" << summaryPath << std::endl;

  Simulator::Destroy();
  return 0;
}
