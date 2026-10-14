using System;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using UnityEngine;

public class UDPHandReceiver : MonoBehaviour
{
    [Header("Paramètres d'affichage")]
    public GameObject landmarkPrefab;
    public float handScale = 5f;
    public Material lineMaterial; // Matériel pour les lignes du squelette
    public Camera mainCamera; // Référence à la caméra
    public float smoothingSpeed = 30f; // Variable lissage (plus élevée = plus rapide)

    private GameObject[] landmarks;
    private LineRenderer[] lines;

    // Définition des connexions du squelette MediaPipe
    private readonly int[,] connections = new int[,]
    {
        {0, 1}, {1, 2}, {2, 3}, {3, 4},       // Pouce
        {0, 5}, {5, 6}, {6, 7}, {7, 8},       // Index
        {5, 9}, {9, 10}, {10, 11}, {11, 12},  // Majeur
        {9, 13}, {13, 14}, {14, 15}, {15, 16},// Annulaire
        {13, 17}, {17, 18}, {18, 19}, {19, 20},// Auriculaire
        {0, 17}                               // Base de la paume
    };

    // Réseau et Threads
    private UdpClient udpClient;
    private Thread receiveThread;
    private bool isRunning = false;

    // Données partagées (Thread-safe)
    private float[] latestData = new float[63];
    private readonly object dataLock = new object();
    private bool hasNewData = false;

    void Start()
    {
        // 1. Instanciation des 21 repères
        landmarks = new GameObject[21];
        for (int i = 0; i < 21; i++)
        {
            landmarks[i] = Instantiate(landmarkPrefab, transform);
            landmarks[i].name = "Landmark_" + i;
        }

        // 2. Initialisation des lignes (squelette)
        int numLines = connections.GetLength(0);
        lines = new LineRenderer[numLines];
        for (int i = 0; i < numLines; i++)
        {
            GameObject lineObj = new GameObject("Line_" + i);
            lineObj.transform.SetParent(transform);
            LineRenderer lr = lineObj.AddComponent<LineRenderer>();

            // Configuration visuelle de la ligne
            lr.startWidth = 0.015f;
            lr.endWidth = 0.015f;
            lr.material = lineMaterial != null ? lineMaterial : new Material(Shader.Find("Sprites/Default"));
            lr.positionCount = 2;
            lines[i] = lr;
        }

        // 3. Initialisation du serveur UDP
        try
        {
            udpClient = new UdpClient(5065);
            isRunning = true;
            receiveThread = new Thread(ReceiveData);
            receiveThread.IsBackground = true;
            receiveThread.Start();
            Debug.Log("Serveur UDP démarré sur le port 5065.");
        }
        catch (Exception e)
        {
            Debug.LogError("Erreur d'initialisation UDP : " + e.Message);
        }
    }

    void ReceiveData()
    {
        IPEndPoint anyIP = new IPEndPoint(IPAddress.Any, 0);
        while (isRunning)
        {
            try
            {
                byte[] data = udpClient.Receive(ref anyIP);
                if (data.Length == 252)
                {
                    lock (dataLock)
                    {
                        for (int i = 0; i < 63; i++)
                        {
                            latestData[i] = BitConverter.ToSingle(data, i * 4);
                        }
                        hasNewData = true;
                    }
                }
            }
            catch (SocketException) { }
            catch (Exception e) { Debug.LogWarning("Erreur : " + e.Message); }
        }
    }

    void Update()
    {
        lock (dataLock)
        {
            if (!hasNewData) return;
            hasNewData = false;

            // Mise à jour des positions des sphères
            for (int i = 0; i < 21; i++)
            {
                float x = (latestData[i * 3] - 0.5f) * handScale;
                float y = -(latestData[i * 3 + 1] - 0.5f) * handScale;
                float z = latestData[i * 3 + 2] * handScale;

                Vector3 targetPosition = new Vector3(x, y, z);
                landmarks[i].transform.localPosition = Vector3.Lerp(landmarks[i].transform.localPosition, targetPosition, Time.deltaTime * smoothingSpeed);
            }

            // Mise à jour des lignes du squelette
            for (int i = 0; i < lines.Length; i++)
            {
                int startIndex = connections[i, 0];
                int endIndex = connections[i, 1];
                lines[i].SetPosition(0, landmarks[startIndex].transform.position);
                lines[i].SetPosition(1, landmarks[endIndex].transform.position);
            }

            // Suivi de la caméra (centré sur la paume, repère 0)
            if (mainCamera != null)
            {
                Vector3 targetCamPos = landmarks[0].transform.position + new Vector3(0, 0, -5f);
                mainCamera.transform.position = Vector3.Lerp(mainCamera.transform.position, targetCamPos, Time.deltaTime * 5f);
            }
        }
    }

    void OnApplicationQuit()
    {
        isRunning = false;
        if (udpClient != null) udpClient.Close();
        if (receiveThread != null && receiveThread.IsAlive) receiveThread.Join(500);
    }
}
