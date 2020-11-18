#                     Copyright © 2020 Joseph Policarpio

#     Server for Battle Anki, an addon for Anki, a program for studying flash cards.

#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU Affero General Public License (AGPL)
#     version 3 of the License, as published by the Free Software Foundation.
#                               AGPL-3.0-only.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU Affero General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>.


import socket
import select
import threading
import json
import schedule
import time

port = 54321  # <-- input port of your server here
server = '123.456.7.890'  # <-- input IP address of your server here

header = 32
msg_format = 'utf-8'
disconn_msg = 'Disconnected'

print(f'[SERVER NAME] {socket.gethostname()}\n'
      f'[SERVER IP] {server} on port {port}')
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
print(f'[SERVER] Socket Created')

utd_ver = "1.20"
connected_dict = {'utd_ver': utd_ver,
                  'clients connected': []}
clients = []
threads = []
t = {}

# masterlock = threading.RLock()
threadlocker = threading.Lock()


def dict_to_str(in_dict: dict):
    try:
        out_str = json.dumps(in_dict, indent=2)
        return out_str
    except json.JSONDecodeError as jsonerr:
        print(f'there was a problem dict_to_str\n'
              f'{jsonerr}')


def str_to_dict(in_str: str):
    try:
        out_dict = json.loads(in_str)
        return out_dict
    except json.JSONDecodeError as jsonerro:
        print(f'there was a problem str_to_dict\n'
              f'{jsonerro}')


def check_socks(readables=None, writeables=None, exceptioners=None, tmout: float = 0.0):
    try:
        if readables is None:
            readables = []
        if writeables is None:
            writeables = []
        if exceptioners is None:
            exceptioners = []
        ready_reads, ready_writes, in_errors = select.select(readables, writeables, exceptioners, tmout)
        return [ready_reads, ready_writes, in_errors]
    except:
        print(f'****** Problem in check_socks')


class Handle:

    def __init__(self, conn, client_ip_addr):
        # super().__init__(*args, **kwargs)
        self.conn = conn
        self.client_ip_addr = client_ip_addr

    def receive_client_dict(self, msg):
        try:
            new_msg = True
            full_msg = ''
            msg_len = int(self.conn.recv(header))
            while len(full_msg) < msg_len:
                chunk = self.conn.recv(msg_len - len(full_msg))
                if chunk == b'':
                    break
                full_msg += chunk.decode(msg_format)
            print(f'[SERVER] Received: {len(full_msg) + header} bytes')
            if len(full_msg) != msg_len:
                return False
            if len(full_msg) == msg_len:
                return full_msg
        except Exception as ex:
            print(ex)
            return False

    def handle_client(self):
        print(f'[NEW THREAD] {threading.current_thread().name} is now active...')
        client_ip_str = str(self.client_ip_addr)
        print(f'[NEW CONNECTION] from {self.client_ip_addr}')
        connected = True
        while connected:
            try:
                socks_ready = check_socks(readables=[self.conn], tmout=30.0)
                if len(socks_ready[0]) > 0:
                    conn_sock = socks_ready[0][0]
                    received_str = self.receive_client_dict(conn_sock)
                    if received_str is False:
                        break
                    if received_str is not None:
                        if received_str == disconn_msg:
                            try:
                                connected = False
                                print(f"[HANDLE THREAD] sending to remove_closed_client\n"
                                      f"......{client_ip_str}......")
                            except:
                                print(f'there was a problem receiving the disconn_msg')
                            finally:
                                break
                        else:
                            try:
                                client_dict = {}
                                rec_data_str = str(received_str)
                                client_dict = str_to_dict(rec_data_str)
                                if client_dict['ver'] is not None:
                                    if int(client_dict['ver'][-2:]) >= 16:
                                        pass
                                    else:
                                        connected = False
                                        break
                                else:
                                    connected = False
                                    break
                                client_dict['user info']['Public IP'] = client_ip_str
                                client_dict['alive'] = (int(time.time()))
                                client_dict['current CST:'] = time.asctime(time.localtime())
                                if not client_dict['window open']:
                                    client_dict['window open'] = False
                                update_db(self.conn, client_dict)
                                user_name = str(client_dict['user info']['name'])
                                if client_dict['user info']['progress'] is not None:
                                    progress = str(client_dict['user info']['progress'])
                                else:
                                    progress = "NOprog"
                                if client_dict['request options']['req name'] is not None:
                                    req_name = str(client_dict['request options']['req name'])
                                else:
                                    req_name = "NOreq"
                                print(f'[{user_name}][{client_ip_str}] {progress} {req_name}')
                            except (TypeError, ValueError) as err:
                                print(f'there was a problem responding to the client\n'
                                      f'{err}')
            except Exception as er:
                print(f'there was a problem in handle_client\n'
                      f'{er}')
        try:
            threadlocker.acquire()
            remove_closed_client(self.conn, client_ip_str)
        finally:
            threadlocker.release()
        print(f'oooooooooooooooooooooooooooooooooooooooooooooooooooo\n'
              f'{dict_to_str(connected_dict)}\n'
              f'oooooooooooooooooooooooooooooooooooooooooooooooooooo\n'
              f'[THREAD DYING] {threading.current_thread().name} is now DYING...\n'
              f'[CLIENTS]: {len(clients)} [ACT CONNS]: {threading.active_count() - 2} '
              f'[TOT ACT THREADS]: {threading.active_count() - 1}')
        print("[CONNECTION] to client lost")


class Heart:
    # def __init__(self):

    def server_send(self, conn, tot_msg):
        total_sent = 0
        try:
            while total_sent < len(tot_msg):
                sent = conn.send(tot_msg[total_sent:])
                if sent == 0:
                    remove_closed_client(conn)
                    print('[SERVER] Unable to send a full message... LN-235')
                    break
                total_sent += sent
        except:
            print(f'****** Problem in server_send')

    def broadcast(self):
        global clients
        msg = dict_to_str(connected_dict)
        msg_whead = f'{len(msg):<{header}}' + msg
        msg_send = msg_whead.encode(msg_format)
        try:
            threadlocker.acquire()
            if len(connected_dict['clients connected']) > 0:
                three_lists_avail = check_socks(writeables=clients)
                can_write = three_lists_avail[1]
                if len(can_write) > 0:
                    for conn in can_write:
                        try:
                            self.server_send(conn, msg_send)
                        except TypeError as LN229:
                            print(f'exception in broadcast fxn ln 312'
                                  f'trying to remove from broadcast list'
                                  f'{LN229}')
                            try:
                                clients.remove(conn)
                                print(f'[SERVER] REMOVING CONN from broadcast:\n'
                                      f'{str(conn)}\n')
                            except Exception as LN237:
                                print(f'{LN237}')
                print(f'[BROADCAST TO]: {len(can_write)} '
                      f'[ACT CONNS]: {threading.active_count() - 2}')
        except Exception as ln243:
            print(f'{ln243}')
        finally:
            threadlocker.release()

    def print_clients(self):
        print(f'\n..............{time.asctime(time.localtime())}..............\n'
              f'----------------------------------------------------\n'
              f'{dict_to_str(connected_dict)}\n'
              f'----------------------------------------------------\n'
              f'[CLIENTS]: {len(clients)} [ACT CONNS]: {threading.active_count() - 2} '
              f'[TOT ACT THREADS]: {threading.active_count()}\n')


def remove_closed_client(conn: socket, ip_to_close: str = None):
    global connected_dict
    global clients
    #  THREADLOCKING DONE OUTSIDE OF FXN
    try:
        if conn is not None:
            # try:
            #     threadlocker.acquire()
            if conn in clients:
                clients.remove(conn)
            conn.close()
            # finally:
            #     threadlocker.release()
            print(f"\n[SERVER] removed CONN from broadcast list:\n"
                  f"{conn}")
        if ip_to_close is not None:
            if (len(connected_dict['clients connected'])) > 0:
                # try:
                #     threadlocker.acquire()
                for y in range(0, len(connected_dict['clients connected'])):
                    if connected_dict['clients connected'][y]['user info']['Remote IP'] == ip_to_close:
                        del connected_dict['clients connected'][y]
                        print(f"\n[SERVER] GOODBYE {ip_to_close}\n")
                        break
                # finally:
                #     threadlocker.release()
    except Exception as er:
        print(str(er))


def update_db(conn: socket = None, client_dict: dict = None):
    global connected_dict
    global clients  # sockets for broadcasting, not IPs for local method
    new_ip = None
    client_ips = []
    try:
        if client_dict is not None:
            if conn is not None:
                if conn not in clients:
                    clients.append(conn)
            if client_dict['user info']['Remote IP'] is not None:
                new_ip = str(client_dict['user info']['Remote IP'])
                if len(connected_dict['clients connected']) == 0:
                    connected_dict['clients connected'].append(client_dict)
                    print(f"[SERVER] received a NEW client connection")
                if len(connected_dict['clients connected']) > 0:
                    for x in range(0, len(connected_dict['clients connected'])):
                        con_ip = str(connected_dict['clients connected'][x]['user info']['Remote IP'])
                        client_ips.append(con_ip)
                        # if incoming dict is already in all_clients list, update it...
                        if new_ip == con_ip:
                            connected_dict['clients connected'][x] = None
                            connected_dict['clients connected'][x] = client_dict
                            print(f"[SERVER] UPDATED a client dictionary")
                    if new_ip not in client_ips:
                        connected_dict['clients connected'].append(client_dict)
                        print(f"[SERVER] received a NEW client connection")
    except TypeError:
        pass


def kill_dead_clients():
    global connected_dict
    try:
        if len(connected_dict['clients connected']) > 0:
            try:
                threadlocker.acquire()
                for i in range(0, len(connected_dict['clients connected'])):
                    elapsed = int(time.time()) - int(connected_dict['clients connected'][i]['alive'])
                    if elapsed > 7:
                        dead_ip = connected_dict['clients connected'][i]['user info']['Remote IP']
                        del connected_dict['clients connected'][i]
                        print(f'[SERVER] client {dead_ip} timed out\n'
                              f'[CLIENTS] {len(clients)} [ACT CONNS] NOW {threading.active_count() - 2} '
                              f'[TOTAL THREADS] {threading.active_count()}')
                        break
            finally:
                threadlocker.release()
    except Exception as exceptt:
        print(str(exceptt))


def server_heartbeat():
    print(f'[NEW THREAD] {threading.current_thread().name} is now active...')
    try:
        while True:
            schedule.run_pending()
            time.sleep(0.5)
    except Exception as yu:
        print(f'[THREAD DYING] {threading.current_thread().name} is now DYING...'
              f'{yu}')


def start_server():
    global clients
    s.listen(10)
    print(f'[LISTENING] Listening on {server}...')
    n = 0
    while True:
        try:
            n += 1
            conn, client_ip_addr = s.accept()
            t[f'Client_{int(n)}'] = {}
            t[f'Client_{int(n)}']['class'] = Handle(conn, client_ip_addr)
            t[f'Client_{int(n)}']['thread'] = threading.Thread(target=t[f'Client_{int(n)}']['class'].handle_client,
                                                               name=f'Client_{int(n)}')
            t[f'Client_{int(n)}']['thread'].start()
            if conn is not None:
                if conn not in clients:
                    clients.append(conn)
            print(f'[ACT CONNS] {threading.active_count() - 2}')
        except KeyboardInterrupt:
            print('\n\n[SERVER] a HUMAN interrupted me!\n\n')
            exit()
        except Exception as exc:
            print(str(exc))


try:
    s.bind((server, port))
except socket.error as e:
    print(e)


try:
    hrt = Heart()
    schedule.every(15).seconds.do(hrt.print_clients)
    # schedule.every(4).seconds.do(update_db)
    schedule.every(3).seconds.do(kill_dead_clients)
    schedule.every(2.4).seconds.do(hrt.broadcast)
    hb = threading.Thread(target=server_heartbeat, daemon=True, name="Heartbeat Thread")
    hb.start()
    start_server()
    print('[STARTING] The server is starting...\n')
except RuntimeError as rter:
    print(f'Runtime Error: {rter}')
except Exception as ze:
    print(ze)
